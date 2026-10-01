from pathlib import Path
import hashlib,json
r=Path(__file__).resolve().parents[1];v=r/'BMMS_V12';lab=r/'V12_npu_lab/narrow_dense'
base=(v/'v12_baseline_r41.asc').read_bytes().decode()
a=base.index('class RowMaxConsumer {',base.index('namespace bmms1230 {'));b=base.index('} // namespace bmms1230',a)
consumer=base[a:b]
consumer=consumer.replace('pipe->InitBuffer(runningBuf,(AM/2)*4);','pipe->InitBuffer(runningBuf,(p.M/2)*4);')
consumer=consumer.replace('int seq=0;auto rows=rowBuf.Get<float>(),run=runningBuf.Get<float>();','int seq=0;auto rows=rowBuf.Get<float>();')
consumer=consumer.replace('const int ar=MinI(AM,mEnd-mBase),vr=ar/2;','const int ar=MinI(AM,mEnd-mBase),vr=ar/2;\n                auto run=runningBuf.Get<float>()[mBase/2];')
start=consumer.index('                bmms71::Fence<AscendC::HardEvent::V_MTE3>(*pipe_);')
end=consumer.index('        bmms71::Fence<AscendC::HardEvent::MTE3_MTE2>(*pipe_);AscendC::SyncAll<true>();',start)
consumer=consumer[:start]+'''            }
            // pM=1 and tasks=blocks: each AIV owns one half of every M macro.
            // Commit its packed row maxima after all Cube ring reads complete.
            bmms71::Fence<AscendC::HardEvent::V_MTE3>(*pipe_);
            const int full=p.M/AM,tail=p.M%AM;
            auto packed=runningBuf.Get<float>();
            const int64_t dst=(int64_t(batch)*p.pN+ns)*p.M;
            if(full){
                AscendC::DataCopyExtParams cp{uint16_t(full),uint32_t((AM/2)*4),0,uint32_t((AM/2)*4),0};
                AscendC::DataCopyPad(part[dst+sub*(AM/2)],packed,cp);
            }
            if(tail){
                const int vr=tail/2;
                AscendC::DataCopyExtParams cp{1,uint32_t(vr*4),0,0,0};
                AscendC::DataCopyPad(part[dst+full*AM+sub*vr],packed[full*(AM/2)],cp);
            }
            bmms71::Fence<AscendC::HardEvent::MTE3_V>(*pipe_);
        }
'''+consumer[end:]
mod='''// BMMS1250_BEGIN
namespace bmms1250 {
using Plan=bmms1230::Plan;using bmms1230::MakePlan;using bmms83::MinI;
constexpr int AM=bmms1230::AM,BN=bmms1230::BN,MACRO_ELEMS=bmms1230::MACRO_ELEMS;
constexpr int READY=bmms1230::READY,FREE=bmms1230::FREE;
static inline bool Eligible(int B,int M,int N,int K,int cores){
    if(cores<2||!bmms1230::Eligible(B,M,N,K,cores)||
       !(M>=1280&&M<1536&&N>=4096&&N<6144&&K>=1536&&K<1664)||
       bmms1241::Eligible(B,M,N,K,cores))return false;
    const auto p=MakePlan(B,M,N,K,cores);
    return p.pM==1&&p.pN>=4&&p.tasks==p.blocks;
}
'''+consumer+'''
template<class T,bool TA,bool TB>
__aicore__ inline void Entry(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ring,GM_ADDR part,Plan p){
    AscendC::TPipe pipe;
    if ASCEND_IS_AIC {bmms1230::MacroMmadProducer<T,TA,TB> op;op.Init(a,b,ring,p,&pipe);op.Process();}
    if ASCEND_IS_AIV {RowMaxConsumer op;op.Init(ring,part,y,p,&pipe);op.Process();}
}
}
'''
a=base.index('#define BMMS1230_KERNEL');b=base.index('// BMMS1230_END',a)
mod+=base[a:b].replace('1230','1250').replace('!AlignedPitch(','!bmms1230::AlignedPitch(')+'// BMMS1250_END\n\n'
hook='    if(bmms1250::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
i=base.index('extern "C" void run_kernel(');src=base[:i]+mod+base[i:];i=src.index('    if(bmms1241::TryLaunch');src=src[:i]+hook+src[i:]
assert src.replace(mod,'',1).replace(hook,'',1)==base
name='v12_r50_case12_deferred_partials.asc';(v/name).write_bytes(src.encode());(lab/'r50.asc').write_bytes(src.encode())
meta=dict(version='v12_r50',parent='v12_baseline_r41.asc',sha256=hashlib.sha256(src.encode()).hexdigest(),status='experimental pending validation',change='Retain original r30 producer and grid, keep row maxima in UB across all M macros and write partials in 1-2 strided DMA calls',scope='Case12 r30 domain, r41 gate FALSE, pM=1 pN>=4 tasks=blocks',producer_reused='bmms1230::MacroMmadProducer',parent_byte_recovery=True,new_device_entries=8,final_reduce_equal_to='r30 full-M merge and ReduceSum')
(v/'v12_r50_manifest.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
cm=(lab/'CMakeLists.txt').read_text()
if 'add_executable(bench_r50' not in cm:
    cm+='''
add_executable(bench_r50 main.asc)
target_compile_definitions(bench_r50 PRIVATE BMMS_KERNEL_HEADER="r50.asc" BMMS_VARIANT="r50")
target_link_libraries(bench_r50 PRIVATE tiling_api register platform unified_dlog dl m graph_base)
target_include_directories(bench_r50 PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_options(bench_r50 PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=dav-2201>)
'''
(lab/'CMakeLists.txt').write_bytes(cm.encode())
script='''#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_narrow_20260929
cmake -S . -B build >logs/r50_configure.log 2>&1
cmake --build build --target bench_r50 -j2 >logs/r50_build.log 2>&1
for pair in 'manifest correctness' 'extra extra_correctness' 'r41_holdout holdout_correctness' 'r47_all special_correctness' 'r48_holdout new_correctness'; do
    read -r manifest tag <<< "$pair"
    ./build/bench_r50 cases/$manifest.txt 3 results/r50_$tag.jsonl >logs/r50_$tag.log 2>&1
done
python3 run_screen.py --baseline r41 --candidate r50 --manifest cases/r48_holdout.txt --tag r50_screen --repeats 30 --discard 5 --windows 2 >logs/r50_screen.log 2>&1
echo R50_DONE
'''
(lab/'check_r50.sh').write_bytes(script.encode());print(json.dumps(meta))

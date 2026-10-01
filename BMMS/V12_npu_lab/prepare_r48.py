from pathlib import Path
import hashlib,json
r=Path(__file__).resolve().parents[1];v=r/'BMMS_V12';lab=r/'V12_npu_lab/narrow_dense';o=r/'V12_npu_lab/results/parallel_epilogue_20260929';o.mkdir(exist_ok=True)
base=(v/'v12_baseline_r41.asc').read_bytes().decode()
a=base.index('class RowMaxConsumer {',base.index('namespace bmms1230 {'));b=base.index('} // namespace bmms1230',a)
consumer=base[a:b]
prefix=consumer[:consumer.index('        auto merged=mergedBuf.Get<float>(),tmp=tmpBuf.Get<float>();')]
prefix=prefix.replace('ring,part,out;','ring,part,out,finalRows;')
prefix=prefix.replace('rowBuf,sumBuf;','rowBuf,sumBuf,finalScratch;')
prefix=prefix.replace('AscendC::TBuf<AscendC::TPosition::VECIN> mergedBuf,tmpBuf;','AscendC::TBuf<AscendC::TPosition::VECIN> packedBuf;\n    AscendC::TBuf<AscendC::TPosition::VECOUT> mergedBuf;')
prefix=prefix.replace('        out.SetGlobalBuffer(', '        finalRows.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(pt)+int64_t(p.B)*p.pN*p.M,p.M);\n        out.SetGlobalBuffer(')
prefix=prefix.replace('pipe->InitBuffer(mergedBuf,p.M*4);pipe->InitBuffer(tmpBuf,p.M*4);pipe->InitBuffer(sumBuf,p.M*4);','pipe->InitBuffer(packedBuf,p.pN*ROW*4);pipe->InitBuffer(mergedBuf,ROW*4);\n        pipe->InitBuffer(sumBuf,p.M*4);pipe->InitBuffer(finalScratch,p.M*4);')
tail='''        auto packed=packedBuf.Get<float>(),merged=mergedBuf.Get<float>();
        for(int mStart=worker*ROW;mStart<p.M;mStart+=2*p.blocks*ROW){
            const int vr=MinI(ROW,p.M-mStart);
            AscendC::DataCopyExtParams cp{uint16_t(p.pN),uint32_t(vr*4),uint32_t((p.M-vr)*4),uint32_t((ROW-vr)/8),0};
            AscendC::DataCopyPadExtParams<float> pd{false,0,0,0.0f};
            AscendC::DataCopyPad(packed,part[mStart],cp,pd);
            bmms71::Fence<AscendC::HardEvent::MTE2_V>(*pipe_);
            AscendC::Max(merged,packed,packed,vr);AscendC::PipeBarrier<PIPE_V>();
            for(int ns=1;ns<p.pN;++ns){
                AscendC::Max(merged,merged,packed[ns*ROW],vr);AscendC::PipeBarrier<PIPE_V>();
            }
            bmms71::Fence<AscendC::HardEvent::V_MTE3>(*pipe_);
            AscendC::DataCopyExtParams save{1,uint32_t(vr*4),0,0,0};
            AscendC::DataCopyPad(finalRows[mStart],merged,save);
            bmms71::Fence<AscendC::HardEvent::MTE3_V>(*pipe_);
            bmms71::Fence<AscendC::HardEvent::V_MTE2>(*pipe_);
        }
        bmms71::Fence<AscendC::HardEvent::MTE3_MTE2>(*pipe_);AscendC::SyncAll<true>();
        if(worker==0){
            auto all=sumBuf.Get<float>();
            AscendC::DataCopyExtParams cp{1,uint32_t(p.M*4),0,0,0};
            AscendC::DataCopyPadExtParams<float> pd{false,0,0,0.0f};
            AscendC::DataCopyPad(all,finalRows,cp,pd);
            bmms71::Fence<AscendC::HardEvent::MTE2_V>(*pipe_);
            auto yy=oq.AllocTensor<float>();
            AscendC::ReduceSum(yy,all,finalScratch.Get<float>(),p.M);
            oq.EnQue(yy);yy=oq.DeQue<float>();
            AscendC::DataCopyExtParams cpOut{1,4,0,0,0};
            AscendC::DataCopyPad(out,yy,cpOut);oq.FreeTensor(yy);
        }
    }
};
'''
mod='''// BMMS1248_BEGIN
namespace bmms1248 {
using Plan=bmms1230::Plan;using bmms1230::MakePlan;using bmms83::MinI;
constexpr int AM=bmms1230::AM,BN=bmms1230::BN,MACRO_ELEMS=bmms1230::MACRO_ELEMS;
constexpr int READY=bmms1230::READY,FREE=bmms1230::FREE,ROW=64;
static inline bool Eligible(int B,int M,int N,int K,int cores){
    return cores>=2&&bmms1230::Eligible(B,M,N,K,cores)&&
        M>=1280&&M<1536&&N>=4096&&N<6144&&K>=1536&&K<1664&&
        !bmms1241::Eligible(B,M,N,K,cores);
}
static inline uint64_t WorkspaceBytes(const Plan& p){return bmms11r2::WorkspaceBytes(p)+uint64_t(p.M)*4;}
'''+prefix+tail+'''
template<class T,bool TA,bool TB>
__aicore__ inline void Entry(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ring,GM_ADDR part,Plan p){
    AscendC::TPipe pipe;
    if ASCEND_IS_AIC {bmms1230::MacroMmadProducer<T,TA,TB> op;op.Init(a,b,ring,p,&pipe);op.Process();}
    if ASCEND_IS_AIV {RowMaxConsumer op;op.Init(ring,part,y,p,&pipe);op.Process();}
}
}
'''
la=base.index('#define BMMS1230_KERNEL');lb=base.index('// BMMS1230_END',la)
launch=base[la:lb].replace('1230','1248').replace('!AlignedPitch(', '!bmms1230::AlignedPitch(')
launch=launch.replace('bmms11r2::WorkspaceBytes(p)','WorkspaceBytes(p)')
mod+=launch+'// BMMS1248_END\n\n'
hook='    if(bmms1248::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
i=base.index('extern "C" void run_kernel(');src=base[:i]+mod+base[i:];i=src.index('    if(bmms1241::TryLaunch');src=src[:i]+hook+src[i:]
assert src.replace(mod,'',1).replace(hook,'',1)==base
# Arithmetic producer and initial ring/partial reduction body remain byte-identical.
oldprocess=consumer.split('    __aicore__ inline void Process(){',1)[1].split('        auto merged=')[0]
assert oldprocess in mod
name='v12_r48_case12_parallel_epilogue.asc';(v/name).write_bytes(src.encode());(lab/'r48.asc').write_bytes(src.encode())
meta=dict(version='v12_r48',parent='v12_baseline_r41.asc',sha256=hashlib.sha256(src.encode()).hexdigest(),status='experimental pending validation',producer_reused='bmms1230::MacroMmadProducer',initial_consumer_byte_equal=True,parent_byte_recovery=True,scope='Case12 r30 domain with r41 flat gate FALSE',change='Original compute plan and ring producer; packed strided partial loads, row-parallel Max, baseline-order full-M ReduceSum',new_device_entries=8)
(v/'v12_r48_manifest.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
cm=(lab/'CMakeLists.txt').read_text()
if 'add_executable(bench_r48' not in cm:
    cm+='''
add_executable(bench_r48 main.asc)
target_compile_definitions(bench_r48 PRIVATE BMMS_KERNEL_HEADER="r48.asc" BMMS_VARIANT="r48")
target_link_libraries(bench_r48 PRIVATE tiling_api register platform unified_dlog dl m graph_base)
target_include_directories(bench_r48 PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_options(bench_r48 PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=dav-2201>)
'''
(lab/'CMakeLists.txt').write_bytes(cm.encode())
script='''#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_narrow_20260929
cmake -S . -B build >logs/r48_configure.log 2>&1
cmake --build build --target bench_r48 -j2 >logs/r48_build.log 2>&1
for pair in 'manifest correctness' 'extra extra_correctness' 'r41_holdout holdout_correctness' 'r47_all new_correctness'; do
    read -r manifest tag <<< "$pair"
    ./build/bench_r48 cases/$manifest.txt 3 results/r48_$tag.jsonl >logs/r48_$tag.log 2>&1
done
python3 run_screen.py --baseline r41 --candidate r48 --manifest cases/r47_holdout.txt --tag r48_screen --repeats 30 --discard 5 --windows 2 >logs/r48_screen.log 2>&1
echo R48_DONE
'''
(lab/'check_r48.sh').write_bytes(script.encode());print(json.dumps(meta))

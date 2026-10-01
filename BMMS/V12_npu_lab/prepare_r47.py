from pathlib import Path
import hashlib,json,subprocess
r=Path(__file__).resolve().parents[1];v=r/'BMMS_V12';lab=r/'V12_npu_lab/narrow_dense';o=r/'V12_npu_lab/results/b_resident_20260929'
base=(v/'v12_baseline_r41.asc').read_bytes().decode();old=(v/'v12_r46_case12_fractional_n.asc').read_text(encoding='utf-8');a=old.index('// BMMS1246_BEGIN');b=old.index('// BMMS1246_END',a)+len('// BMMS1246_END');mod=old[a:b].replace('1246','1247')
mod=mod.replace('+size_t(2*p.blocks)*8*sizeof(float)', '+size_t(p.M)*sizeof(float)')
mod=mod.replace('ring,part,out,sums;', 'ring,part,out,finalRows;')
mod=mod.replace('AscendC::TBuf<AscendC::TPosition::VECIN> mergedBuf,tmpBuf;\n    AscendC::TBuf<AscendC::TPosition::VECOUT> scalarBuf;',
 'AscendC::TBuf<AscendC::TPosition::VECIN> tmpBuf;\n    AscendC::TBuf<AscendC::TPosition::VECOUT> mergedBuf;')
mod=mod.replace('sums.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(pt)+int64_t(p.blocks)*p.M,int64_t(2*p.blocks)*8);',
 'finalRows.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(pt)+int64_t(p.blocks)*p.M,p.M);')
mod=mod.replace('pipe->InitBuffer(sumBuf,2*p.blocks*8*4);pipe->InitBuffer(scalarBuf,32);\n        pipe->InitBuffer(finalScratch,2*p.blocks*8*4);',
 'pipe->InitBuffer(sumBuf,p.M*4);pipe->InitBuffer(finalScratch,p.M*4);')
mod=mod.replace('        auto scalar=scalarBuf.Get<float>();\n        float localSum=0.0f;\n','')
a=mod.index('            AscendC::ReduceSum(scalar,merged,sumBuf.Get<float>(),vr);');b=mod.index('\n    }\n};',a)
mod=mod[:a]+'''            bmms71::Fence<AscendC::HardEvent::V_MTE3>(*pipe_);
            AscendC::DataCopyExtParams cp{1,uint32_t(vr*4),0,0,0};
            AscendC::DataCopyPad(finalRows[mStart],merged,cp);
            bmms71::Fence<AscendC::HardEvent::MTE3_V>(*pipe_);
        }
        bmms71::Fence<AscendC::HardEvent::MTE3_MTE2>(*pipe_);AscendC::SyncAll<true>();
        if(worker==0){
            auto all=sumBuf.Get<float>();
            AscendC::DataCopyExtParams cp{1,uint32_t(p.M*4),0,0,0};
            AscendC::DataCopyPadExtParams<float> pd{false,0,0,0.0f};
            AscendC::DataCopyPad(all,finalRows,cp,pd);
            bmms71::Fence<AscendC::HardEvent::MTE2_V>(*pipe_);
            auto yy=oq.AllocTensor<float>();
            // Preserve the baseline's full-M ReduceSum, including its length/order.
            AscendC::ReduceSum(yy,all,finalScratch.Get<float>(),p.M);
            oq.EnQue(yy);yy=oq.DeQue<float>();
            AscendC::DataCopyExtParams outCopy{1,4,0,0,0};
            AscendC::DataCopyPad(out,yy,outCopy);oq.FreeTensor(yy);
        }
'''+mod[b:]
payload=mod+'\n\n';i=base.index('extern "C" void run_kernel(');src=base[:i]+payload+base[i:]
hook='    if(bmms1247::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n';i=src.index('    if(bmms1241::TryLaunch');src=src[:i]+hook+src[i:]
assert src.replace(payload,'',1).replace(hook,'',1)==base
name='v12_r47_case12_fractional_rows.asc';(v/name).write_bytes(src.encode());(lab/'r47.asc').write_bytes(src.encode())
meta=dict(version='v12_r47',parent='v12_baseline_r41.asc',sha256=hashlib.sha256(src.encode()).hexdigest(),status='experimental pending NPU validation',parent_byte_recovery=True,scope='Case12 domain, original r30 guards, r41 gate FALSE',change='128-column scheduling units and sparse parallel row Max; full-M baseline ReduceSum preserved',new_device_entries=8)
(v/'v12_r47_manifest.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
cm=(lab/'CMakeLists.txt').read_text(encoding='utf-8')
if 'add_executable(bench_r47' not in cm:cm+='''
add_executable(bench_r47 main.asc)
target_compile_definitions(bench_r47 PRIVATE BMMS_KERNEL_HEADER="r47.asc" BMMS_VARIANT="r47")
target_link_libraries(bench_r47 PRIVATE tiling_api register platform unified_dlog dl m graph_base)
target_include_directories(bench_r47 PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_options(bench_r47 PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=dav-2201>)
'''
(lab/'CMakeLists.txt').write_bytes(cm.encode())
prefix=(o/'audit_r46.cpp').read_text(encoding='utf-8').split('int main(){')[0]
code=prefix+'''int main(){for(int M=1280;M<1536;M+=16)for(int N=4096;N<6144;N+=16)if(bmms1246::Eligible(1,M,N,1536,20))printf("%d %d\\n",M,N);}\n'''
(o/'r47_candidates.cpp').write_text(code,encoding='utf-8');subprocess.run(['g++','-O2','-std=c++17',str(o/'r47_candidates.cpp'),'-o',str(o/'r47_candidates.exe')],check=True)
rows=subprocess.check_output([str(o/'r47_candidates.exe')]);(lab/'r47_candidates.txt').write_bytes(rows)
script='''#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_narrow_20260929
TORCH_DEVICE_BACKEND_AUTOLOAD=0 python3 generate_r47.py >logs/r47_generate.log 2>&1
cmake -S . -B build >logs/r47_configure.log 2>&1
cmake --build build --target bench_r47 -j2 >logs/r47_build.log 2>&1
./build/bench_r47 cases/manifest.txt 3 results/r47_correctness.jsonl >logs/r47_correctness.log 2>&1
./build/bench_r47 cases/extra.txt 3 results/r47_extra_correctness.jsonl >logs/r47_extra_correctness.log 2>&1
./build/bench_r47 cases/r41_holdout.txt 3 results/r47_holdout_correctness.jsonl >logs/r47_holdout_correctness.log 2>&1
./build/bench_r41 cases/r47_all.txt 3 results/r47_new_baseline_correctness.jsonl >logs/r47_new_baseline_correctness.log 2>&1
./build/bench_r47 cases/r47_all.txt 3 results/r47_new_correctness.jsonl >logs/r47_new_correctness.log 2>&1
python3 run_screen.py --baseline r41 --candidate r47 --manifest cases/r42_screen.txt --tag r47_screen --repeats 30 --discard 5 --windows 2 >logs/r47_screen.log 2>&1
python3 run_screen.py --baseline r41 --candidate r47 --manifest cases/r47_holdout.txt --tag r47_holdout --repeats 30 --discard 5 --windows 2 >logs/r47_holdout.log 2>&1
echo R47_DONE
'''
(lab/'check_r47.sh').write_bytes(script.encode());print(json.dumps(meta))

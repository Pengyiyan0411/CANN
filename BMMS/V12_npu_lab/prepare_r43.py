from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V12';lab=root/'V12_npu_lab/narrow_dense'
base=(v/'v12_baseline_r41.asc').read_bytes().decode()
a=base.index('// BMMS1219_BEGIN');b=base.index('// BMMS1219_END',a)+len('// BMMS1219_END')
mod=base[a:b].replace('1219','1243')
mod=mod.replace('int32_t seq=0;bool cPending=false;','int32_t seq=0;bool cPending=false;\n    bool l1Prefetched=false;int l1Start=0;')
mod=mod.replace('void Macro(int group,int batch,int m0,int n0,int ar,int br){','void Macro(int group,int batch,int m0,int n0,int ar,int br,int nextM,int nextN,int nextAr,int nextBr,bool hasNext){')
mod=mod.replace('''        int l0Count=0;
        LoadStage(batch,m0,n0,ar,br,0,MinI(K1,p.K),0);''','''        int l0Count=0;const int start=l1Start;
        if(!l1Prefetched)LoadStage(batch,m0,n0,ar,br,0,MinI(K1,p.K),start);
        l1Prefetched=false;''')
mod=mod.replace('const int s1=ki&1,kBase=ki*K1','const int s1=(ki&1)^start,kBase=ki*K1')
needle='''                LoadStage(batch,m0,n0,ar,br,nextK,MinI(K1,p.K-nextK),next);
            }'''
replacement='''                LoadStage(batch,m0,n0,ar,br,nextK,MinI(K1,p.K-nextK),next);
            }else if(hasNext){
                const int next=s1^1;
                if(kCount>=2)AscendC::WaitFlag<AscendC::HardEvent::MTE1_MTE2>(l1Free[next]);
                LoadStage(batch,nextM,nextN,nextAr,nextBr,0,MinI(K1,p.K),next);
                l1Start=next;l1Prefetched=true;
            }'''
assert mod.count(needle)==1;mod=mod.replace(needle,replacement)
needle='        for(int s=0;s<MinI(2,kCount);++s)AscendC::WaitFlag<AscendC::HardEvent::MTE1_MTE2>(l1Free[s]);'
replacement='''        if(hasNext){
            // Preserve the other slot's READY for the prefetched next macro.
            const int last=((kCount-1)&1)^start;
            AscendC::WaitFlag<AscendC::HardEvent::MTE1_MTE2>(l1Free[last]);
        }else{
            for(int s=0;s<MinI(2,kCount);++s)
                AscendC::WaitFlag<AscendC::HardEvent::MTE1_MTE2>(l1Free[s^start]);
            l1Start=0;
        }'''
assert mod.count(needle)==1;mod=mod.replace(needle,replacement)
needle='''            for(int m0=mBegin;m0<mEnd;m0+=AM)for(int n0=nBegin;n0<nEnd;n0+=BN)
                Macro(group,batch,m0,n0,MinI(AM,mEnd-m0),MinI(BN,nEnd-n0));'''
replacement='''            for(int m0=mBegin;m0<mEnd;m0+=AM)for(int n0=nBegin;n0<nEnd;n0+=BN){
                const int nextN=n0+BN<nEnd?n0+BN:nBegin;
                const int nextM=n0+BN<nEnd?m0:m0+AM;
                const bool hasNext=nextM<mEnd;
                // Stop the inherited prefetch state at each task boundary.
                Macro(group,batch,m0,n0,MinI(AM,mEnd-m0),MinI(BN,nEnd-n0),
                    nextM,nextN,hasNext?MinI(AM,mEnd-nextM):0,
                    hasNext?MinI(BN,nEnd-nextN):0,hasNext);
            }'''
assert mod.count(needle)==1;mod=mod.replace(needle,replacement)
payload=mod+'\n\n';i=base.index('extern "C" void run_kernel(');src=base[:i]+payload+base[i:]
oldhook='    if(bmms1219::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;'
assert src.count(oldhook)==1
hook=oldhook.replace('1219','1243')+'\n';src=src.replace(oldhook,hook+oldhook)
assert src.replace(payload,'',1).replace(hook,'',1)==base
name='v12_r43_case8_nz_prefetch.asc';(v/name).write_bytes(src.encode());(lab/'r43.asc').write_bytes(src.encode())
meta=dict(version='v12_r43',parent='v12_baseline_r41.asc',sha256=hashlib.sha256(src.encode()).hexdigest(),status='research: pending validation; not recommended',parent_byte_recovery=True,change='r19 route only: next macro first L1 stage prefetch; pack inputs, plan, microtile MMAD and masked consumer unchanged',new_device_entries=8)
(v/'v12_r43_manifest.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
cm=(lab/'CMakeLists.txt').read_text(encoding='utf-8')
if 'add_executable(bench_r43' not in cm:cm+='''
add_executable(bench_r43 main.asc)
target_compile_definitions(bench_r43 PRIVATE BMMS_KERNEL_HEADER="r43.asc" BMMS_VARIANT="r43")
target_link_libraries(bench_r43 PRIVATE tiling_api register platform unified_dlog dl m graph_base)
target_include_directories(bench_r43 PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_options(bench_r43 PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=dav-2201>)
'''
(lab/'CMakeLists.txt').write_bytes(cm.encode())
script='''#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_narrow_20260929
TORCH_DEVICE_BACKEND_AUTOLOAD=0 python3 generate_r43.py >logs/r43_generate.log 2>&1
cmake -S . -B build >logs/r43_configure.log 2>&1
cmake --build build --target bench_r43 -j2 >logs/r43_build.log 2>&1
./build/bench_r43 cases/manifest.txt 3 results/r43_correctness.jsonl >logs/r43_correctness.log 2>&1
./build/bench_r43 cases/extra.txt 3 results/r43_extra_correctness.jsonl >logs/r43_extra_correctness.log 2>&1
./build/bench_r43 cases/r41_holdout.txt 3 results/r43_holdout_correctness.jsonl >logs/r43_holdout_correctness.log 2>&1
./build/bench_r43 cases/r43_all.txt 3 results/r43_c8_correctness.jsonl >logs/r43_c8_correctness.log 2>&1
python3 run_screen.py --baseline r41 --candidate r43 --manifest cases/r43_screen.txt --tag r43_screen --repeats 30 --discard 5 --windows 2 >logs/r43_screen.log 2>&1
echo R43_SCREEN_DONE
'''
(lab/'check_r43.sh').write_bytes(script.encode());print(json.dumps(meta))

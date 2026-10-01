from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V12';lab=root/'V12_npu_lab/narrow_dense'
base=(v/'v12_baseline_r41.asc').read_bytes().decode()
a=base.index('// BMMS1241_BEGIN');b=base.index('// BMMS1241_END',a)+len('// BMMS1241_END')
mod=base[a:b].replace('1241','1242')
mod=mod.replace('TM=64,TN=128,AM=128,BN=256,K1=256,K0=64','TM=32,TN=128,AM=64,BN=256,K1=384,K0=64')
a=mod.index('static inline bool Eligible(');b=mod.index('static inline bool AlignedPitch(',a)
mod=mod[:a]+'''static inline bool Eligible(int B,int M,int N,int K,int cores){
    return cores>=2&&bmms1230::Eligible(B,M,N,K,cores)&&
        M>=1280&&M<1536&&N>=4096&&N<6144&&K>=1536&&K<1664;
}
static inline Plan MakePlan(int B,int M,int N,int K,int cores){
    auto p=bmms11r2::MakePlan(B,M,N,K,cores);
    p.mTiles=bmms83::UpH(M,AM);p.nTiles=bmms83::UpH(N,BN);
    p.blocks=bmms83::MinH(cores,p.mTiles*p.nTiles);p.pM=1;p.pN=p.blocks;p.tasks=p.blocks;return p;
}
static inline size_t RingBytes(const Plan& p){return size_t(p.blocks)*2*MACRO_ELEMS*sizeof(float);}
static inline size_t WorkspaceBytes(const Plan& p){return RingBytes(p)+size_t(p.blocks)*p.M*sizeof(float);}
'''+mod[b:]
mod=mod.replace('l0Free[2],cReady,cFree;', 'l0Free[2],cReady[2],cFree[2];')
mod=mod.replace('int32_t seq=0;bool cPending=false;', 'int32_t seq=0;')
mod=mod.replace('if(cPending){AscendC::WaitFlag<AscendC::HardEvent::FIX_M>(cFree);cPending=false;}',
    'if(l0Count==0&&seq>=2)AscendC::WaitFlag<AscendC::HardEvent::FIX_M>(cFree[seq&1]);')
mod=mod.replace('AscendC::Mmad(cBuf.template Get<float>(),aa,bb,q);','AscendC::Mmad(cBuf.template Get<float>()[(seq&1)*MACRO_ELEMS],aa,bb,q);')
mod=mod.replace('AscendC::SetFlag<AscendC::HardEvent::M_FIX>(cReady);','AscendC::SetFlag<AscendC::HardEvent::M_FIX>(cReady[seq&1]);')
mod=mod.replace('AscendC::WaitFlag<AscendC::HardEvent::M_FIX>(cReady);','AscendC::WaitFlag<AscendC::HardEvent::M_FIX>(cReady[seq&1]);')
mod=mod.replace('cBuf.template Get<float>(),f);','cBuf.template Get<float>()[macroSlot*MACRO_ELEMS],f);')
mod=mod.replace('AscendC::SetFlag<AscendC::HardEvent::FIX_M>(cFree);cPending=true;','AscendC::SetFlag<AscendC::HardEvent::FIX_M>(cFree[macroSlot]);')
mod=mod.replace('cReady=pipe->AllocEventID<AscendC::HardEvent::M_FIX>();cFree=pipe->AllocEventID<AscendC::HardEvent::FIX_M>();',
'''for(int s=0;s<2;++s){
            cReady[s]=pipe->AllocEventID<AscendC::HardEvent::M_FIX>();
            cFree[s]=pipe->AllocEventID<AscendC::HardEvent::FIX_M>();
        }''')
mod=mod.replace('InitBuffer(cBuf,4*TM*TN*sizeof(float))','InitBuffer(cBuf,2*MACRO_ELEMS*sizeof(float))')
mod=mod.replace('if(cPending)AscendC::WaitFlag<AscendC::HardEvent::FIX_M>(cFree);','for(int s=0;s<MinI(2,seq);++s)AscendC::WaitFlag<AscendC::HardEvent::FIX_M>(cFree[s]);')
mod=mod.replace('pipe_->ReleaseEventID<AscendC::HardEvent::M_FIX>(cReady);pipe_->ReleaseEventID<AscendC::HardEvent::FIX_M>(cFree);',
'''for(int s=0;s<2;++s){
            pipe_->ReleaseEventID<AscendC::HardEvent::M_FIX>(cReady[s]);
            pipe_->ReleaseEventID<AscendC::HardEvent::FIX_M>(cFree[s]);
        }''')
mod=mod.replace('bmms11r2::WorkspaceBytes(p)','WorkspaceBytes(p)').replace('bmms11r2::RingBytes(p)','RingBytes(p)')
assert 'cPending' not in mod
payload=mod+'\n\n';i=base.index('extern "C" void run_kernel(');src=base[:i]+payload+base[i:]
hook='    if(bmms1242::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
i=src.index('    if(bmms1241::TryLaunch');src=src[:i]+hook+src[i:]
assert src.replace(payload,'',1).replace(hook,'',1)==base
name='v12_r42_wide_halfm_pingpong.asc';(v/name).write_bytes(src.encode());(lab/'r42.asc').write_bytes(src.encode())
meta=dict(version='v12_r42',parent='v12_baseline_r41.asc',sha256=hashlib.sha256(src.encode()).hexdigest(),status='research: pending validation; not recommended',parent_byte_recovery=True,change='Case12 domain only: flattened64x256 macro, K1=384,K0=64,double L0C; full K sum and max-N/sum-M retained',L1_bytes=491520,L0A_bytes=16384,L0B_bytes=65536,L0C_bytes=131072,new_device_entries=8)
(v/'v12_r42_manifest.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
cm=(lab/'CMakeLists.txt').read_text(encoding='utf-8')
if 'add_executable(bench_r42' not in cm: cm+='''
add_executable(bench_r42 main.asc)
target_compile_definitions(bench_r42 PRIVATE BMMS_KERNEL_HEADER="r42.asc" BMMS_VARIANT="r42")
target_link_libraries(bench_r42 PRIVATE tiling_api register platform unified_dlog dl m graph_base)
target_include_directories(bench_r42 PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_options(bench_r42 PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=dav-2201>)
'''
(lab/'CMakeLists.txt').write_bytes(cm.encode())
script='''#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_narrow_20260929
cmake -S . -B build >logs/r42_configure.log 2>&1
cmake --build build --target bench_r42 -j2 >logs/r42_build.log 2>&1
./build/bench_r42 cases/manifest.txt 3 results/r42_correctness.jsonl >logs/r42_correctness.log 2>&1
./build/bench_r42 cases/extra.txt 3 results/r42_extra_correctness.jsonl >logs/r42_extra_correctness.log 2>&1
./build/bench_r42 cases/r41_holdout.txt 3 results/r42_holdout_correctness.jsonl >logs/r42_holdout_correctness.log 2>&1
awk '$3 >= 1280 && $3 < 1536 && $4 >= 4096 && $4 < 6144 && $5 >= 1536 && $5 < 1664' cases/r41_holdout.txt >cases/r42_screen.txt
python3 run_screen.py --baseline r41 --candidate r42 --manifest cases/r42_screen.txt --tag r42_screen --repeats 30 --discard 5 --windows 2 >logs/r42_screen.log 2>&1
echo R42_DONE
'''
(lab/'check_r42.sh').write_bytes(script.encode());print(json.dumps(meta))

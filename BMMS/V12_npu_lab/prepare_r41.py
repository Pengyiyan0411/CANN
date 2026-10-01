from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V12';lab=root/'V12_npu_lab/narrow_dense'
base=(v/'v12_baseline_r33.asc').read_bytes().decode()
a=base.index('// BMMS1230_BEGIN');b=base.index('// BMMS1230_END',a)+len('// BMMS1230_END')
module=base[a:b].replace('1230','1241')
elig='return B==1&&M>=1024&&M<2048&&N>=2048&&N<=8192&&K>=1536&&K<4096&&bmms11r2::Eligible(B,M,N,K,cores);'
newelig='''if(!bmms1230::Eligible(B,M,N,K,cores)||cores<2)return false;
    if(!((M>=1536&&M<1792&&N>=2048&&N<3072&&K>=2048&&K<2560)||
         (M>=1280&&M<1536&&N>=4096&&N<6144&&K>=1536&&K<1664)))return false;
    const auto old=bmms11r2::MakePlan(B,M,N,K,cores);
    return uint64_t(bmms83::UpH(old.mTiles*old.nTiles,cores))<bmms11r2::ExistingPeak(old).tiles;'''
assert elig in module;module=module.replace(elig,newelig)
module=module.replace('static inline Plan MakePlan(int B,int M,int N,int K,int cores){return bmms11r2::MakePlan(B,M,N,K,cores);}',
'''static inline Plan MakePlan(int B,int M,int N,int K,int cores){
    auto p=bmms11r2::MakePlan(B,M,N,K,cores);
    p.blocks=bmms83::MinH(cores,p.mTiles*p.nTiles);p.pM=1;p.pN=p.blocks;p.tasks=p.blocks;return p;
}''')
# Contiguous flattened macro ranges partition all output tiles without overlap.
start=module.index('        const int group=AscendC::GetBlockIdx(),perBatch=p.pM*p.pN;')
end=module.index('        for(int s=0;s<MinI(2,seq);++s)',start)
module=module[:start]+'''        const int group=AscendC::GetBlockIdx(),total=p.mTiles*p.nTiles;
        const int first=group*total/p.blocks,last=(group+1)*total/p.blocks;
        for(int tile=first;tile<last;++tile){
            const int m0=(tile/p.nTiles)*AM,n0=(tile%p.nTiles)*BN;
            const bool hasNext=tile+1<last;
            const int nextM=((tile+1)/p.nTiles)*AM,nextN=((tile+1)%p.nTiles)*BN;
            Macro(group,0,m0,n0,MinI(AM,p.M-m0),MinI(BN,p.N-n0),
                nextM,nextN,hasNext?MinI(AM,p.M-nextM):0,hasNext?MinI(BN,p.N-nextN):0,hasNext);
        }
'''+module[end:]
# Each AIV owns one half of every logical row tile. The packed M/2 row vector
# is neutral on untouched rows and merged across producer groups at the end.
module=module.replace('pipe->InitBuffer(rowBuf,(AM/2)*4);pipe->InitBuffer(runningBuf,(AM/2)*4);',
 'pipe->InitBuffer(rowBuf,(AM/2)*4);pipe->InitBuffer(runningBuf,(p.M/2)*4);')
start=module.index('        const int worker=AscendC::GetBlockIdx(),group=worker/2,sub=worker%2;',module.index('class RowMaxConsumer'))
end=module.index('        bmms71::Fence<AscendC::HardEvent::MTE3_MTE2>',start)
# Retain the already-tested half-macro DMA and reduction sequence.
mid=module[module.index('                    AscendC::CrossCoreWaitFlag<0x2>',start):module.index('                    cq.FreeTensor(c);++seq;',start)]
mid=mid.replace('AscendC::Max(run,run,rows,vr);','AscendC::Max(run[mBase/2],run[mBase/2],rows,vr);')
new='''        const int worker=AscendC::GetBlockIdx(),group=worker/2,sub=worker%2;
        const int total=p.mTiles*p.nTiles,first=group*total/p.blocks,last=(group+1)*total/p.blocks;
        int seq=0;auto rows=rowBuf.Get<float>(),run=runningBuf.Get<float>();
        AscendC::Duplicate(run,bmmmaxsum_v43::NEG_INF,p.M/2);AscendC::PipeBarrier<PIPE_V>();
        for(int tile=first;tile<last;++tile){
            const int mBase=(tile/p.nTiles)*AM,nBase=(tile%p.nTiles)*BN;
            const int ar=MinI(AM,p.M-mBase),vr=ar/2,br=MinI(BN,p.N-nBase),ringSlot=seq&1;
'''+mid+'''            cq.FreeTensor(c);++seq;
        }
        bmms71::Fence<AscendC::HardEvent::V_MTE3>(*pipe_);
        // Write every row exactly once, including neutral rows not owned by this group.
        for(int mBase=0;mBase<p.M;mBase+=AM){
            const int vr=MinI(AM,p.M-mBase)/2;
            AscendC::DataCopyExtParams cp{1,uint32_t(vr*4),0,0,0};
            AscendC::DataCopyPad(part[int64_t(group)*p.M+mBase+sub*vr],run[mBase/2],cp);
        }
'''
module=module[:start]+new+module[end:]
insert=base.index('extern "C" void run_kernel(')
src=base[:insert]+module+'\n\n'+base[insert:]
hook='    if(bmms1230::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;'
newhook=hook.replace('1230','1241')+'\n'+hook
assert src.count(hook)==1;src=src.replace(hook,newhook)
assert src.replace(module+'\n\n','',1).replace(newhook,hook,1)==base
name='v12_r41_dense_flat_macro.asc';(v/name).write_bytes(src.encode());(lab/'r41.asc').write_bytes(src.encode())
(v/'v12_r41_manifest.json').write_text(json.dumps(dict(version='v12_r41',parent='v12_baseline_r33.asc',sha256=hashlib.sha256(src.encode()).hexdigest(),status='experimental pending NPU tests',new_device_entries=8,source_byte_recovery=True),indent=2),encoding='utf-8')
cm=(lab/'CMakeLists.txt').read_text(encoding='utf-8');assert 'add_executable(bench_r41' not in cm
cm+='''\nadd_executable(bench_r41 main.asc)
target_compile_definitions(bench_r41 PRIVATE BMMS_KERNEL_HEADER="r41.asc" BMMS_VARIANT="r41")
target_link_libraries(bench_r41 PRIVATE tiling_api register platform unified_dlog dl m graph_base)
target_include_directories(bench_r41 PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_options(bench_r41 PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=dav-2201>)
'''
(lab/'CMakeLists.txt').write_bytes(cm.encode())
script='''#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_narrow_20260929
cmake -S . -B build >logs/r41_configure.log 2>&1
cmake --build build --target bench_r41 -j2 >logs/r41_build.log 2>&1
./build/bench_r41 cases/manifest.txt 3 results/r41_correctness.jsonl >logs/r41_correctness.log 2>&1
./build/bench_r41 cases/extra.txt 3 results/r41_extra_correctness.jsonl >logs/r41_extra_correctness.log 2>&1
./build/bench_r41 cases/r41_holdout.txt 3 results/r41_holdout_correctness.jsonl >logs/r41_holdout_correctness.log 2>&1
python3 run_screen.py --baseline r33 --candidate r41 --manifest cases/holdout.txt --tag r41_discovery --repeats 30 --discard 5 --windows 2 >logs/r41_discovery.log 2>&1
python3 run_screen.py --baseline r33 --candidate r41 --manifest cases/r41_holdout.txt --tag r41_holdout --repeats 30 --discard 5 --windows 2 >logs/r41_holdout.log 2>&1
echo R41_DONE
'''
(lab/'check_r41.sh').write_bytes(script.encode())
print('Prepared',name,hashlib.sha256(src.encode()).hexdigest())

from pathlib import Path
import hashlib,json
r=Path(__file__).resolve().parents[1];v=r/'BMMS_V12';lab=r/'V12_npu_lab/narrow_dense'
base=(v/'v12_baseline_r41.asc').read_bytes().decode();a=base.index('// BMMS1241_BEGIN');b=base.index('// BMMS1241_END',a)+len('// BMMS1241_END');mod=base[a:b].replace('1241','1246')
a=mod.index('static inline bool Eligible(');b=mod.index('static inline bool AlignedPitch(',a)
mod=mod[:a]+'''static inline bool Eligible(int B,int M,int N,int K,int cores){
    return cores>=2&&bmms1230::Eligible(B,M,N,K,cores)&&
        M>=1280&&M<1536&&N>=4096&&N<6144&&K>=1536&&K<1664&&
        !bmms1241::Eligible(B,M,N,K,cores);
}
static inline Plan MakePlan(int B,int M,int N,int K,int cores){
    auto p=bmms11r2::MakePlan(B,M,N,K,cores);
    // nTiles counts 128-column scheduling units, coalesced up to BN in the kernel.
    p.nTiles=bmms83::UpH(N,128);p.blocks=bmms83::MinH(cores,p.mTiles*p.nTiles);
    p.pM=1;p.pN=p.blocks;p.tasks=p.blocks;return p;
}
static inline size_t RingBytes(const Plan& p){return size_t(p.blocks)*2*MACRO_ELEMS*sizeof(float);}
static inline size_t WorkspaceBytes(const Plan& p){return RingBytes(p)+size_t(p.blocks)*p.M*sizeof(float)+size_t(2*p.blocks)*8*sizeof(float);}
'''+mod[b:]
# Keep the verified full 128x256 / K256/64 arithmetic and L1 pipeline.
a=mod.index('        for(int tile=first;tile<last;++tile){');b=mod.index('        for(int s=0;s<MinI(2,seq);++s)',a)
mod=mod[:a]+'''        for(int tile=first;tile<last;){
            const int row=tile/p.nTiles,col=tile%p.nTiles;
            const int units=MinI(2,MinI(last-tile,p.nTiles-col));
            const int m0=row*AM,n0=col*128,br=MinI(units*128,p.N-n0);
            const int nextTile=tile+units;const bool hasNext=nextTile<last;
            const int nextM=(nextTile/p.nTiles)*AM,nextN=(nextTile%p.nTiles)*128;
            const int nextUnits=hasNext?MinI(2,MinI(last-nextTile,p.nTiles-nextTile%p.nTiles)):0;
            Macro(group,0,m0,n0,MinI(AM,p.M-m0),br,nextM,nextN,
                hasNext?MinI(AM,p.M-nextM):0,hasNext?MinI(nextUnits*128,p.N-nextN):0,hasNext);
            tile=nextTile;
        }
'''+mod[b:]
mod=mod.replace('AscendC::GlobalTensor<float> ring,part,out;','AscendC::GlobalTensor<float> ring,part,out,sums;')
mod=mod.replace('AscendC::TBuf<AscendC::TPosition::VECIN> mergedBuf,tmpBuf;', 'AscendC::TBuf<AscendC::TPosition::VECIN> mergedBuf,tmpBuf;\n    AscendC::TBuf<AscendC::TPosition::VECOUT> scalarBuf;\n    AscendC::TBuf<AscendC::TPosition::VECCALC> finalScratch;')
needle='''        out.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(y),p.B);'''
mod=mod.replace(needle,needle+'''
        sums.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(pt)+int64_t(p.blocks)*p.M,int64_t(2*p.blocks)*8);''')
mod=mod.replace('pipe->InitBuffer(mergedBuf,p.M*4);pipe->InitBuffer(tmpBuf,p.M*4);pipe->InitBuffer(sumBuf,p.M*4);',
'''pipe->InitBuffer(mergedBuf,(AM/2)*4);pipe->InitBuffer(tmpBuf,(AM/2)*4);
        pipe->InitBuffer(sumBuf,2*p.blocks*8*4);pipe->InitBuffer(scalarBuf,32);
        pipe->InitBuffer(finalScratch,2*p.blocks*8*4);''')
needle='''        for(int tile=first;tile<last;++tile){
            const int mBase=(tile/p.nTiles)*AM,nBase=(tile%p.nTiles)*BN;
            const int ar=MinI(AM,p.M-mBase),vr=ar/2,br=MinI(BN,p.N-nBase),ringSlot=seq&1;'''
replacement='''        for(int tile=first;tile<last;){
            const int col=tile%p.nTiles,units=MinI(2,MinI(last-tile,p.nTiles-col));
            const int mBase=(tile/p.nTiles)*AM,nBase=col*128;
            const int ar=MinI(AM,p.M-mBase),vr=ar/2,br=MinI(units*128,p.N-nBase),ringSlot=seq&1;'''
assert mod.count(needle)==1;mod=mod.replace(needle,replacement)
mod=mod.replace('cq.FreeTensor(c);++seq;','cq.FreeTensor(c);++seq;tile+=units;')
a=mod.index('        auto merged=mergedBuf.Get<float>(),tmp=tmpBuf.Get<float>();');b=mod.index('\n    }\n};',a)
mod=mod[:a]+'''        // Each row-half is reduced by one worker. Read only groups whose
        // flattened scheduling ranges intersect this M tile, not all groups.
        auto merged=mergedBuf.Get<float>(),tmp=tmpBuf.Get<float>();
        auto scalar=scalarBuf.Get<float>();
        float localSum=0.0f;
        for(int job=worker;job<2*p.mTiles;job+=2*p.blocks){
            const int row=job/2,half=job%2,mBase=row*AM,ar=MinI(AM,p.M-mBase),vr=ar/2;
            const int mStart=mBase+half*vr;
            const int rowFirst=row*p.nTiles,rowLast=(row+1)*p.nTiles;
            const int gFirst=((rowFirst+1)*p.blocks-1)/total;
            const int gLast=(rowLast*p.blocks-1)/total;
            AscendC::Duplicate(merged,bmmmaxsum_v43::NEG_INF,vr);AscendC::PipeBarrier<PIPE_V>();
            for(int g=gFirst;g<=gLast;++g){
                bmms71::Fence<AscendC::HardEvent::V_MTE2>(*pipe_);
                AscendC::DataCopyExtParams cp{1,uint32_t(vr*4),0,0,0};
                AscendC::DataCopyPadExtParams<float> pd{false,0,0,0.0f};
                AscendC::DataCopyPad(tmp,part[int64_t(g)*p.M+mStart],cp,pd);
                bmms71::Fence<AscendC::HardEvent::MTE2_V>(*pipe_);
                AscendC::Max(merged,merged,tmp,vr);AscendC::PipeBarrier<PIPE_V>();
            }
            AscendC::ReduceSum(scalar,merged,sumBuf.Get<float>(),vr);
            bmms71::Fence<AscendC::HardEvent::V_S>(*pipe_);
            localSum+=scalar.GetValue(0);
        }
        scalar.SetValue(0,localSum);
        bmms71::Fence<AscendC::HardEvent::S_MTE3>(*pipe_);
        AscendC::DataCopyExtParams scalarCopy{1,4,0,0,0};
        AscendC::DataCopyPad(sums[int64_t(worker)*8],scalar,scalarCopy);
        bmms71::Fence<AscendC::HardEvent::MTE3_MTE2>(*pipe_);AscendC::SyncAll<true>();
        if(worker==0){
            auto all=sumBuf.Get<float>();
            AscendC::DataCopyExtParams cp{static_cast<uint16_t>(2*p.blocks),4,28,0,0};
            AscendC::DataCopyPadExtParams<float> pd{true,0,7,0.0f};
            AscendC::DataCopyPad(all,sums,cp,pd);
            bmms71::Fence<AscendC::HardEvent::MTE2_V>(*pipe_);
            auto yy=oq.AllocTensor<float>();
            // DMA stores each scalar in its own padded 8-float row, padding zero.
            AscendC::ReduceSum(yy,all,finalScratch.Get<float>(),2*p.blocks*8);
            oq.EnQue(yy);yy=oq.DeQue<float>();
            AscendC::DataCopyPad(out,yy,scalarCopy);oq.FreeTensor(yy);
        }
'''+mod[b:]
mod=mod.replace('bmms11r2::WorkspaceBytes(p)','WorkspaceBytes(p)').replace('bmms11r2::RingBytes(p)','RingBytes(p)')
payload=mod+'\n\n';i=base.index('extern "C" void run_kernel(');src=base[:i]+payload+base[i:]
hook='    if(bmms1246::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
i=src.index('    if(bmms1241::TryLaunch');src=src[:i]+hook+src[i:]
assert src.replace(payload,'',1).replace(hook,'',1)==base
name='v12_r46_case12_fractional_n.asc';(v/name).write_bytes(src.encode());(lab/'r46.asc').write_bytes(src.encode())
meta=dict(version='v12_r46',parent='v12_baseline_r41.asc',sha256=hashlib.sha256(src.encode()).hexdigest(),status='experimental pending NPU validation',parent_byte_recovery=True,scope='Case12 domain, original r30 guards, r41 gate FALSE',change='128-column scheduling units coalesced to original128x256 macro; parallel sparse row Max, then scalar Sum',new_device_entries=8)
(v/'v12_r46_manifest.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
cm=(lab/'CMakeLists.txt').read_text(encoding='utf-8')
if 'add_executable(bench_r46' not in cm:cm+='''
add_executable(bench_r46 main.asc)
target_compile_definitions(bench_r46 PRIVATE BMMS_KERNEL_HEADER="r46.asc" BMMS_VARIANT="r46")
target_link_libraries(bench_r46 PRIVATE tiling_api register platform unified_dlog dl m graph_base)
target_include_directories(bench_r46 PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_options(bench_r46 PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=dav-2201>)
'''
(lab/'CMakeLists.txt').write_bytes(cm.encode())
script='''#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_narrow_20260929
cmake -S . -B build >logs/r46_configure.log 2>&1
cmake --build build --target bench_r46 -j2 >logs/r46_build.log 2>&1
./build/bench_r46 cases/manifest.txt 3 results/r46_correctness.jsonl >logs/r46_correctness.log 2>&1
./build/bench_r46 cases/extra.txt 3 results/r46_extra_correctness.jsonl >logs/r46_extra_correctness.log 2>&1
./build/bench_r46 cases/r41_holdout.txt 3 results/r46_holdout_correctness.jsonl >logs/r46_holdout_correctness.log 2>&1
python3 run_screen.py --baseline r41 --candidate r46 --manifest cases/r42_screen.txt --tag r46_screen --repeats 30 --discard 5 --windows 2 >logs/r46_screen.log 2>&1
echo R46_DONE
'''
(lab/'check_r46.sh').write_bytes(script.encode());print(json.dumps(meta))

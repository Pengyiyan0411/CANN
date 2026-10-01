from pathlib import Path
import hashlib,json
r=Path(__file__).resolve().parents[1];v=r/'BMMS_V12';lab=r/'V12_npu_lab/narrow_dense'
base=(v/'v12_baseline_r41.asc').read_bytes().decode();template=(v/'v12_r42_wide_halfm_pingpong.asc').read_text(encoding='utf-8')
a=template.index('// BMMS1242_BEGIN');b=template.index('// BMMS1242_END',a)+len('// BMMS1242_END');mod=template[a:b].replace('1242','1245')
mod=mod.replace('TM=32,TN=128,AM=64,BN=256,K1=384,K0=64','TM=64,TN=64,AM=128,BN=128,K1=192,K0=64')
mod=mod.replace('M>=1280&&M<1536&&N>=4096&&N<6144&&K>=1536&&K<1664;',
'''M>=1280&&M<1536&&N>=4096&&N<6144&&K>=1536&&K<1664&&
        !bmms1241::Eligible(B,M,N,K,cores);''')
a=mod.index('static inline Plan MakePlan(');b=mod.index('static inline size_t RingBytes',a)
mod=mod[:a]+'''static inline Plan MakePlan(int B,int M,int N,int K,int cores){
    // Keep the original 128x256 macro-grid ownership. Each original N macro
    // is processed as two 128-wide subpanels, with N outside M for B reuse.
    return bmms11r2::MakePlan(B,M,N,K,cores);
}
'''+mod[b:]
mod=mod.replace('size_t(p.blocks)*p.M*sizeof(float)','size_t(p.B)*p.pN*p.M*sizeof(float)')
a=mod.index('    __aicore__ inline void LoadStage(');b=mod.index('    __aicore__ inline void LoadL0(',a)
mod=mod[:a]+'''    __aicore__ inline void LoadB(int batch,int n0,int br){
        AscendC::Nd2NzParams q{};q.ndNum=1;
        q.nValue=TB?br:p.K;q.dValue=TB?p.K:br;
        q.srcDValue=TB?p.K:p.N;q.dstNzC0Stride=TB?br:p.K;q.dstNzNStride=1;
        const int64_t off=int64_t(batch)*p.K*p.N+(TB?int64_t(n0)*p.K:n0);
        AscendC::DataCopy(b1Buf.template Get<T>(),b[off],q);
        // The first following A-stage READY also covers this preceding B copy.
    }
    __aicore__ inline void LoadStage(int batch,int m0,int n0,int ar,int br,int k0,int kr,int s){
        auto aa=a1Buf.template Get<T>()[s*AM*K1];
        AscendC::Nd2NzParams qa{};qa.ndNum=1;
        qa.nValue=TA?kr:ar;qa.dValue=TA?ar:kr;
        qa.srcDValue=TA?p.M:p.K;qa.dstNzC0Stride=TA?kr:ar;qa.dstNzNStride=1;
        const int64_t ai=int64_t(batch)*p.M*p.K+(TA?int64_t(k0)*p.M+m0:int64_t(m0)*p.K+k0);
        AscendC::DataCopy(aa,a[ai],qa);
        AscendC::SetFlag<AscendC::HardEvent::MTE2_MTE1>(l1Ready[s]);
    }

'''+mod[b:]
mod=mod.replace('int kr1,int kk,int kr0,int s1,int s0)', 'int kr1,int kk,int bk,int kr0,int s1,int s0)')
mod=mod.replace('auto sb=b1Buf.template Get<T>()[s1*K1*BN];','auto sb=b1Buf.template Get<T>();')
mod=mod.replace('lb.srcStride=TB?1:kr1/16;', 'lb.srcStride=TB?1:p.K/16;')
mod=mod.replace('TB?(kk/16+j)*br*16:(kk+j*16)*16','TB?(bk/16+j)*br*16:(bk+j*16)*16')
mod=mod.replace('LoadL0(ar,br,kr1,kk,kr0,s1,s0);','LoadL0(ar,br,kr1,kk,kBase+kk,kr0,s1,s0);')
mod=mod.replace('pipe->InitBuffer(b1Buf,2*K1*BN*sizeof(T));','pipe->InitBuffer(b1Buf,p.K*BN*sizeof(T));')
a=mod.index('        const int group=AscendC::GetBlockIdx(),total=');b=mod.index('        for(int s=0;s<MinI(2,seq);++s)',a)
mod=mod[:a]+'''        const int group=AscendC::GetBlockIdx(),perBatch=p.pM*p.pN;
        for(int task=group;task<p.tasks;task+=p.blocks){
            const int batch=task/perBatch,slot=task-batch*perBatch,ms=slot/p.pN,ns=slot-ms*p.pN;
            const int mt0=ms*p.mTiles/p.pM,mt1=(ms+1)*p.mTiles/p.pM;
            const int nt0=ns*p.nTiles/p.pN,nt1=(ns+1)*p.nTiles/p.pN;
            const int mBegin=mt0*AM,mEnd=MinI(mt1*AM,p.M);
            const int nBegin=nt0*256,nEnd=MinI(nt1*256,p.N);
            for(int n0=nBegin;n0<nEnd;n0+=BN){
                const int br=MinI(BN,nEnd-n0);
                LoadB(batch,n0,br);
                for(int m0=mBegin;m0<mEnd;m0+=AM){
                    const int nextM=m0+AM;const bool hasNext=nextM<mEnd;
                    Macro(group,batch,m0,n0,MinI(AM,mEnd-m0),br,
                        nextM,n0,hasNext?MinI(AM,mEnd-nextM):0,br,hasNext);
                }
                // Last macro drained both A stages and L0 readers before replacing B.
            }
        }
'''+mod[b:]
a=mod.index('        const int worker=AscendC::GetBlockIdx(),group=worker/2,sub=worker%2;');b=mod.index('        bmms71::Fence<AscendC::HardEvent::MTE3_MTE2>(*pipe_);AscendC::SyncAll<true>();',a)
mod=mod[:a]+'''        const int worker=AscendC::GetBlockIdx(),group=worker/2,sub=worker%2;
        const int perBatch=p.pM*p.pN;int seq=0;
        auto rows=rowBuf.Get<float>(),run=runningBuf.Get<float>();
        for(int task=group;task<p.tasks;task+=p.blocks){
            const int batch=task/perBatch,slot=task-batch*perBatch,ms=slot/p.pN,ns=slot-ms*p.pN;
            const int mt0=ms*p.mTiles/p.pM,mt1=(ms+1)*p.mTiles/p.pM;
            const int nt0=ns*p.nTiles/p.pN,nt1=(ns+1)*p.nTiles/p.pN;
            const int mBegin=mt0*AM,mEnd=MinI(mt1*AM,p.M);
            const int nBegin=nt0*256,nEnd=MinI(nt1*256,p.N);
            AscendC::Duplicate(run,bmmmaxsum_v43::NEG_INF,p.M/2);AscendC::PipeBarrier<PIPE_V>();
            for(int nBase=nBegin;nBase<nEnd;nBase+=BN)for(int mBase=mBegin;mBase<mEnd;mBase+=AM){
                const int ar=MinI(AM,mEnd-mBase),vr=ar/2,br=MinI(BN,nEnd-nBase),ringSlot=seq&1;
                AscendC::CrossCoreWaitFlag<0x2>(READY+ringSlot);
                auto c=cq.AllocTensor<float>();
                AscendC::Duplicate(c,bmmmaxsum_v43::NEG_INF,vr*BN);
                bmms71::Fence<AscendC::HardEvent::V_MTE2>(*pipe_);
                const int64_t off=(int64_t(group)*2+ringSlot)*MACRO_ELEMS+sub*vr*BN;
                AscendC::DataCopyExtParams cp{static_cast<uint16_t>(vr),uint32_t(br*4),uint32_t((BN-br)*4),uint32_t((BN-br)/8),0};
                AscendC::DataCopyPadExtParams<float> pd{false,0,0,0.0f};
                AscendC::DataCopyPad(c,ring[off],cp,pd);cq.EnQue(c);c=cq.DeQue<float>();
                AscendC::CrossCoreSetFlag<0x2,PIPE_MTE2>(FREE+ringSlot);
                AscendC::BinaryRepeatParams rp{1,1,1,16,16,16};
                AscendC::Max(c,c,c[64],64,vr,rp);AscendC::PipeBarrier<PIPE_V>();
                AscendC::WholeReduceMax(rows,c,64,vr,1,1,16,AscendC::ReduceOrder::ORDER_ONLY_VALUE);
                AscendC::PipeBarrier<PIPE_V>();
                AscendC::Max(run[mBase/2],run[mBase/2],rows,vr);AscendC::PipeBarrier<PIPE_V>();
                cq.FreeTensor(c);++seq;
            }
            bmms71::Fence<AscendC::HardEvent::V_MTE3>(*pipe_);
            for(int mBase=mBegin;mBase<mEnd;mBase+=AM){
                const int vr=MinI(AM,mEnd-mBase)/2;
                AscendC::DataCopyExtParams cp{1,uint32_t(vr*4),0,0,0};
                AscendC::DataCopyPad(part[(int64_t(batch)*p.pN+ns)*p.M+mBase+sub*vr],run[mBase/2],cp);
            }
            bmms71::Fence<AscendC::HardEvent::MTE3_V>(*pipe_);
        }
'''+mod[b:]
payload=mod+'\n\n';i=base.index('extern "C" void run_kernel(');src=base[:i]+payload+base[i:]
hook='    if(bmms1245::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
i=src.index('    if(bmms1241::TryLaunch');src=src[:i]+hook+src[i:]
assert src.replace(payload,'',1).replace(hook,'',1)==base
name='v12_r45_case12_b_resident.asc';(v/name).write_bytes(src.encode());(lab/'r45.asc').write_bytes(src.encode())
meta=dict(version='v12_r45',parent='v12_baseline_r41.asc',sha256=hashlib.sha256(src.encode()).hexdigest(),status='experimental, pending NPU validation',parent_byte_recovery=True,scope='Case12 domain plus r30 pitch/family and r41 flat gate FALSE',change='Original grid ownership, 128x128 N subpanels, full K B L1 residency across M, A K1=192 pingpong and double L0C',max_L1_bytes=516096,L0A_bytes=32768,L0B_bytes=32768,L0C_bytes=131072,new_device_entries=8)
(v/'v12_r45_manifest.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
cm=(lab/'CMakeLists.txt').read_text(encoding='utf-8')
if 'add_executable(bench_r45' not in cm:cm+='''
add_executable(bench_r45 main.asc)
target_compile_definitions(bench_r45 PRIVATE BMMS_KERNEL_HEADER="r45.asc" BMMS_VARIANT="r45")
target_link_libraries(bench_r45 PRIVATE tiling_api register platform unified_dlog dl m graph_base)
target_include_directories(bench_r45 PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_options(bench_r45 PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=dav-2201>)
'''
(lab/'CMakeLists.txt').write_bytes(cm.encode())
script='''#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_narrow_20260929
cmake -S . -B build >logs/r45_configure.log 2>&1
cmake --build build --target bench_r45 -j2 >logs/r45_build.log 2>&1
./build/bench_r45 cases/manifest.txt 3 results/r45_correctness.jsonl >logs/r45_correctness.log 2>&1
./build/bench_r45 cases/extra.txt 3 results/r45_extra_correctness.jsonl >logs/r45_extra_correctness.log 2>&1
./build/bench_r45 cases/r41_holdout.txt 3 results/r45_holdout_correctness.jsonl >logs/r45_holdout_correctness.log 2>&1
python3 run_screen.py --baseline r41 --candidate r45 --manifest cases/r42_screen.txt --tag r45_screen --repeats 30 --discard 5 --windows 2 >logs/r45_screen.log 2>&1
echo R45_DONE
'''
(lab/'check_r45.sh').write_bytes(script.encode());print(json.dumps(meta))

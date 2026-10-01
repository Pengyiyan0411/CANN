"""Build the independent N-major/full-K-B-resident Case12 candidate from r41."""
from pathlib import Path
import hashlib,json

root=Path(__file__).resolve().parents[1]
v=root/'BMMS_V12';lab=root/'V12_npu_lab/case12_k1_20261001'
base=(v/'v12_baseline_r41.asc').read_bytes().decode()
assert hashlib.sha256(base.encode()).hexdigest()=='1caf7870ac4154c0f555621ba9c41f4601c6ecee96cb2e8d0bf23acc4fc4f373'
old=(v/'v12_r45_case12_b_resident.asc').read_text()
start=old.index('template<class T,bool TA,bool TB>\nclass MacroMmadProducer',old.index('// BMMS1245_BEGIN'))
end=old.index('class RowMaxConsumer',start)
producer=old[start:end].replace('int s){\n        auto aa=', 'int s,bool fillB){\n        auto aa=',1)
needle='        AscendC::SetFlag<AscendC::HardEvent::MTE2_MTE1>(l1Ready[s]);'
producer=producer.replace(needle,'''        if(fillB){
            static_assert(!TB,"Resident B uses physical KxN");
            AscendC::Nd2NzParams qb{};qb.ndNum=1;qb.nValue=kr;qb.dValue=br;
            qb.srcDValue=p.N;qb.dstNzC0Stride=p.K;qb.dstNzNStride=1;
            // Fill the final full-K NZ position, not a compact K1-stage layout.
            AscendC::DataCopy(b1Buf.template Get<T>()[k0*16],b[int64_t(k0)*p.N+n0],qb);
        }
'''+needle,1)
producer=producer.replace('int nextBr,bool hasNext){','int nextBr,bool hasNext,bool seedB){',1)
producer=producer.replace('MinI(K1,p.K),start);','MinI(K1,p.K),start,seedB);',1)
producer=producer.replace('MinI(K1,p.K-nextK),next);','MinI(K1,p.K-nextK),next,seedB);',1)
producer=producer.replace('MinI(K1,p.K),next);','MinI(K1,p.K),next,false);',1)
a=producer.index('        const int group=AscendC::GetBlockIdx(),perBatch=')
# Preserve the established final ring/L0C drain and event release section.
b=producer.index('        for(int s=0;s<MinI(2,seq);',a)
producer=producer[:a]+'''        const int group=AscendC::GetBlockIdx();
        int first=group*p.totalTiles/p.blocks;
        const int last=(group+1)*p.totalTiles/p.blocks;
        while(first<last){
            const int nt=first/p.mTiles,mt=first%p.mTiles;
            const int runEnd=MinI(last,(nt+1)*p.mTiles);
            const int mBegin=mt*AM,mEnd=MinI((runEnd-nt*p.mTiles)*AM,p.M);
            const int n0=nt*BN,br=MinI(BN,p.N-n0);
            // The previous run drained every L1 reader before B can be overwritten.
            if(!STREAM_B)LoadB(0,n0,br);
            for(int m0=mBegin;m0<mEnd;m0+=AM){
                const int nextM=m0+AM;const bool hasNext=nextM<mEnd;
                Macro(group,0,m0,n0,MinI(AM,mEnd-m0),br,
                    nextM,n0,hasNext?MinI(AM,mEnd-nextM):0,br,hasNext,
                    STREAM_B && m0==mBegin);
            }
            first=runEnd;
        }
'''+producer[b:]

host='''// BMMS1259_BEGIN
// N-major contiguous ownership; B reused across M macros inside each run.
namespace bmms1259 {
using bmms83::MinI;
struct Plan {int32_t B,M,N,K,mTiles,nTiles,totalTiles,blocks;};
constexpr int TM=64,TN=64,AM=128,BN=128,K1=256,K0=64,MACRO_ELEMS=AM*BN;
constexpr bool STREAM_B=true;
constexpr uint16_t READY=4,FREE=6;
static inline bool Eligible(int B,int M,int N,int K,int cores){
    return cores>=2 && cores<=64 && bmms1230::Eligible(B,M,N,K,cores) &&
        M>=1280 && M<1536 && N>=4096 && N<6144 && K==1536 &&
        !bmms1241::Eligible(B,M,N,K,cores);
}
static inline bool AlignedPitch(int M,int N,int K,bool ta,bool tb){
    return !tb && bmms1230::AlignedPitch(M,N,K,ta,tb);
}
static inline Plan MakePlan(int B,int M,int N,int K,int cores){
    Plan p{B,M,N,K,(M+AM-1)/AM,(N+BN-1)/BN,0,cores};
    p.totalTiles=p.mTiles*p.nTiles;return p;
}
static inline uint64_t RingBytes(const Plan& p){return uint64_t(p.blocks)*2*MACRO_ELEMS*4;}
static inline uint64_t PartialBytes(const Plan& p){return uint64_t(p.blocks)*p.M*4;}
static inline uint64_t WorkspaceBytes(const Plan& p){return RingBytes(p)+PartialBytes(p)+uint64_t(p.M)*4;}
static inline uint64_t AppUbBytes(const Plan& p){return 32768ULL+32+256+uint64_t(p.M/2)*4+2ULL*p.M*4+uint64_t(p.blocks)*32*4;}
'''
consumer=r'''
class RowMaxConsumer {
    Plan p;AscendC::TPipe* pipe_;
    AscendC::GlobalTensor<float> ring,part,mergedGm,out;
    AscendC::TQue<AscendC::TPosition::VECIN,1> cq;
    AscendC::TQue<AscendC::TPosition::VECOUT,1> oq;
    AscendC::TBuf<AscendC::TPosition::VECCALC> rowBuf,sumBuf;
    AscendC::TBuf<AscendC::TPosition::VECOUT> runningBuf;
    AscendC::TBuf<AscendC::TPosition::VECIN> mergedBuf,stripeBuf;
public:
    __aicore__ inline void Init(GM_ADDR r,GM_ADDR pt,GM_ADDR merged,GM_ADDR y,const Plan& plan,AscendC::TPipe* pipe){
        p=plan;pipe_=pipe;
        ring.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(r),int64_t(p.blocks)*2*MACRO_ELEMS);
        part.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(pt),int64_t(p.blocks)*p.M);
        mergedGm.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(merged),p.M);
        out.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(y),1);
        pipe->InitBuffer(cq,1,(AM/2)*BN*4);pipe->InitBuffer(oq,1,32);
        pipe->InitBuffer(rowBuf,(AM/2)*4);pipe->InitBuffer(runningBuf,(p.M/2)*4);
        pipe->InitBuffer(mergedBuf,p.M*4);pipe->InitBuffer(sumBuf,p.M*4);
        pipe->InitBuffer(stripeBuf,p.blocks*32*4);
    }
    __aicore__ inline void Process(){
        const int worker=AscendC::GetBlockIdx(),group=worker/2,sub=worker%2;
        const int first=group*p.totalTiles/p.blocks,last=(group+1)*p.totalTiles/p.blocks;
        int seq=0;auto rows=rowBuf.Get<float>(),run=runningBuf.Get<float>();
        AscendC::Duplicate(run,bmmmaxsum_v43::NEG_INF,p.M/2);AscendC::PipeBarrier<PIPE_V>();
        for(int tile=first;tile<last;++tile){
            const int mBase=(tile%p.mTiles)*AM,nBase=(tile/p.mTiles)*BN;
            const int ar=MinI(AM,p.M-mBase),vr=ar/2,br=MinI(BN,p.N-nBase),ringSlot=seq&1;
            AscendC::CrossCoreWaitFlag<0x2>(READY+ringSlot);
            auto c=cq.AllocTensor<float>();
            AscendC::Duplicate(c,bmmmaxsum_v43::NEG_INF,vr*BN);
            bmms71::Fence<AscendC::HardEvent::V_MTE2>(*pipe_);
            const int64_t off=(int64_t(group)*2+ringSlot)*MACRO_ELEMS+sub*vr*BN;
            AscendC::DataCopyExtParams cp{uint16_t(vr),uint32_t(br*4),uint32_t((BN-br)*4),uint32_t((BN-br)/8),0};
            AscendC::DataCopyPadExtParams<float> pd{false,0,0,0.0f};
            AscendC::DataCopyPad(c,ring[off],cp,pd);cq.EnQue(c);c=cq.DeQue<float>();
            AscendC::CrossCoreSetFlag<0x2,PIPE_MTE2>(FREE+ringSlot);
            const AscendC::BinaryRepeatParams rp{1,1,1,16,16,16};
            AscendC::Max(c,c,c[64],64,vr,rp);AscendC::PipeBarrier<PIPE_V>();
            AscendC::WholeReduceMax(rows,c,64,vr,1,1,16,AscendC::ReduceOrder::ORDER_ONLY_VALUE);
            AscendC::PipeBarrier<PIPE_V>();
            AscendC::Max(run[mBase/2],run[mBase/2],rows,vr);AscendC::PipeBarrier<PIPE_V>();
            cq.FreeTensor(c);++seq;
        }
        bmms71::Fence<AscendC::HardEvent::V_MTE3>(*pipe_);
        for(int mBase=0;mBase<p.M;mBase+=AM){
            const int vr=MinI(AM,p.M-mBase)/2;
            AscendC::DataCopyExtParams cp{1,uint32_t(vr*4),0,0,0};
            AscendC::DataCopyPad(part[int64_t(group)*p.M+mBase+sub*vr],run[mBase/2],cp);
        }
        bmms71::Fence<AscendC::HardEvent::MTE3_MTE2>(*pipe_);AscendC::SyncAll<true>();
        auto stripe=stripeBuf.Get<float>();
        // Each output stripe has one owner; retain the original full-M Sum tree.
        for(int m0=worker*32;m0<p.M;m0+=2*p.blocks*32){
            const int count=MinI(32,p.M-m0);
            bmms71::Fence<AscendC::HardEvent::V_MTE2>(*pipe_);
            AscendC::DataCopyExtParams cp{uint16_t(p.blocks),uint32_t(count*4),uint32_t((p.M-count)*4),uint32_t((32-count)/8),0};
            AscendC::DataCopyPadExtParams<float> pd{false,0,0,0.0f};
            AscendC::DataCopyPad(stripe,part[m0],cp,pd);
            bmms71::Fence<AscendC::HardEvent::MTE2_V>(*pipe_);
            for(int g=1;g<p.blocks;++g){
                AscendC::Max(stripe,stripe,stripe[g*32],count);AscendC::PipeBarrier<PIPE_V>();
            }
            bmms71::Fence<AscendC::HardEvent::V_MTE3>(*pipe_);
            AscendC::DataCopyExtParams op{1,uint32_t(count*4),0,0,0};
            AscendC::DataCopyPad(mergedGm[m0],stripe,op);
            bmms71::Fence<AscendC::HardEvent::MTE3_V>(*pipe_);
        }
        bmms71::Fence<AscendC::HardEvent::MTE3_MTE2>(*pipe_);AscendC::SyncAll<true>();
        if(worker==0){
            auto merged=mergedBuf.Get<float>();
            AscendC::DataCopy(merged,mergedGm,p.M);bmms71::Fence<AscendC::HardEvent::MTE2_V>(*pipe_);
            auto yy=oq.AllocTensor<float>();AscendC::ReduceSum(yy,merged,sumBuf.Get<float>(),p.M);
            oq.EnQue(yy);yy=oq.DeQue<float>();AscendC::DataCopyExtParams oc{1,4,0,0,0};
            AscendC::DataCopyPad(out,yy,oc);oq.FreeTensor(yy);bmms71::Fence<AscendC::HardEvent::V_MTE2>(*pipe_);
        }
    }
};
} // namespace bmms1259
namespace bmms1259 {
template<class T,bool TA>
__aicore__ inline void Entry(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ring,GM_ADDR part,GM_ADDR merged,Plan p){
    AscendC::TPipe pipe;
    if ASCEND_IS_AIC {MacroMmadProducer<T,TA,false> op;op.Init(a,b,ring,p,&pipe);op.Process();}
    if ASCEND_IS_AIV {RowMaxConsumer op;op.Init(ring,part,merged,y,p,&pipe);op.Process();}
}
}
#define BMMS1259_KERNEL(NAME,T,TA) \
__schedmode__(1) __global__ __mix__(1,2) void NAME(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ring,GM_ADDR part,GM_ADDR merged,bmms1259::Plan p){bmms1259::Entry<T,TA>(a,b,y,ring,part,merged,p);}
BMMS1259_KERNEL(bmms1259_f16_nn,half,false)
BMMS1259_KERNEL(bmms1259_f16_tn,half,true)
BMMS1259_KERNEL(bmms1259_b16_nn,bfloat16_t,false)
BMMS1259_KERNEL(bmms1259_b16_tn,bfloat16_t,true)
#undef BMMS1259_KERNEL
namespace bmms1259 {
static inline bool TryLaunch(GM_ADDR a,GM_ADDR b,GM_ADDR y,int32_t B,int32_t M,int32_t N,int32_t K,
    int32_t dtype,bool ta,bool tb,int32_t cores,aclrtStream stream){
    if((dtype!=1&&dtype!=2)||!Eligible(B,M,N,K,cores)||!AlignedPitch(M,N,K,ta,tb))return false;
    const auto family=bmms8::Classify(B,M,N,K,ta,tb);
    if(family==bmms8::Family::Resident||family==bmms8::Family::Tiny)return false;
    const auto p=MakePlan(B,M,N,K,cores);uint8_t* ws=nullptr;
    if(p.totalTiles<p.blocks||AppUbBytes(p)>190ULL*1024)return false;
    if(aclrtMalloc(reinterpret_cast<void**>(&ws),WorkspaceBytes(p),ACL_MEM_MALLOC_HUGE_FIRST)!=ACL_SUCCESS)std::abort();
    uint8_t* partial=ws+RingBytes(p);uint8_t* merged=partial+PartialBytes(p);
#define BMMS1259_LAUNCH(NAME) NAME<<<p.blocks,nullptr,stream>>>(a,b,y,ws,partial,merged,p)
    if(dtype==1){if(!ta){BMMS1259_LAUNCH(bmms1259_f16_nn);}else{BMMS1259_LAUNCH(bmms1259_f16_tn);}}
    else{if(!ta){BMMS1259_LAUNCH(bmms1259_b16_nn);}else{BMMS1259_LAUNCH(bmms1259_b16_tn);}}
#undef BMMS1259_LAUNCH
    if(aclrtSynchronizeStream(stream)!=ACL_SUCCESS)std::abort();if(aclrtFree(ws)!=ACL_SUCCESS)std::abort();return true;
}
}
// BMMS1259_END

'''
mod=host+producer+consumer
hook='    if(bmms1259::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
i=base.index('extern "C" void run_kernel(');src=base[:i]+mod+base[i:]
i=src.index('    if(bmms1241::TryLaunch');src=src[:i]+hook+src[i:]
assert src.replace(mod,'',1).replace(hook,'',1)==base
name='v12_r59_case12_nmajor_b_resident.asc'
for p in [v/name,lab/'r59.asc']:
    p.write_bytes(src.encode())
(lab/'r59_module.asc').write_bytes(mod.encode())
meta=dict(version='v12_r59',parent='v12_baseline_r41.asc',file=name,
          sha256=hashlib.sha256(src.encode()).hexdigest(),status='pending NPU verification',
          change='N-major 128x128 flat ownership; full-K B resident filled during first M macro; K1=256; dual L0C; parallel row max merge; original full-M sum',
          new_device_entries=4,parent_byte_recovery=True,L1_bytes=524288,L0A_bytes=32768,L0B_bytes=32768,L0C_bytes=131072)
(v/'v12_r59_manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
cm=(lab/'CMakeLists.txt').read_text()
if 'r58 r59)' not in cm:cm=cm.replace('r57 r58)','r57 r58 r59)')
(lab/'CMakeLists.txt').write_bytes(cm.encode())
(lab/'check_r59.sh').write_text('''#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_case12_k1_20261001
trap 'echo R59_FAILED > results/r59.status' ERR
echo R59_BUILD > results/r59.status
cmake -S . -B build >logs/r59_configure.log 2>&1
cmake --build build --target bench_r59 -j2 >logs/r59_build.log 2>&1
echo R59_PRECISION > results/r59.status
timeout 180 ./build/bench_r59 cases/all.txt 3 results/r59_correctness.jsonl >logs/r59_correctness.log 2>&1
python3 - <<'PY'
import json
from pathlib import Path
specs=json.loads(Path('cases/specs.json').read_text())
rows=[' '.join(str(s[k]) for k in ['id','B','M','N','K','dtype','ta','tb']) for s in specs if s['split']=='screen' and s['dtype']==1 and s['N'] in (4096,4160,5120,6080)]
assert len(rows)==8
Path('cases/r59_first8.txt').write_text('\\n'.join(rows)+'\\n')
PY
echo R59_SCREEN > results/r59.status
python3 run_screen.py --baseline r41 --candidate r59 --manifest cases/r59_first8.txt --tag r59_first8 --repeats 30 --discard 5 --windows 2 >logs/r59_first8.log 2>&1
echo R59_DONE > results/r59.status
''',encoding='utf-8',newline='\n')
print(json.dumps(meta))

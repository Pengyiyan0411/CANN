#pragma once
namespace bmmmaxsum_v43 {constexpr float NEG_INF=-__builtin_inff();}
namespace bmms71 {
constexpr float NEG_INF = -__builtin_inff();
__aicore__ inline int32_t MinI(int32_t a,int32_t b){return a<b?a:b;}
template<AscendC::HardEvent E>
__aicore__ inline void Fence(AscendC::TPipe& pipe){
    const auto id=static_cast<event_t>(pipe.FetchEventID(E));
    AscendC::SetFlag<E>(id); AscendC::WaitFlag<E>(id);
}
// Small resident GEMM: complete inputs in UB, no Cube, system workspace or
// cross-core synchronization. This is a separate shape family, not a fallback
// for arbitrary GEMM. K is padded to a power of two <=128 for vector row sums.
template<class T,bool TA,bool TB>
__aicore__ inline void ResidentDevice(GM_ADDR a,GM_ADDR b,GM_ADDR y,
    int32_t B,int32_t M,int32_t N,int32_t K,int32_t kp,int32_t workers) {
    AscendC::TPipe pipe;
    const int32_t ar=(M*K+15)/16*16,br=(N*K+15)/16*16;
    const int32_t af=(M*K+7)/8*8,bf=(N*K+7)/8*8;
    const int32_t nr=(N+7)/8*8;
    AscendC::TQue<AscendC::TPosition::VECIN,1> iq;
    AscendC::TQue<AscendC::TPosition::VECOUT,1> oq;
    AscendC::TBuf<AscendC::TPosition::VECCALC> floats,indices,packed,prodBuf,values;
    pipe.InitBuffer(iq,1,(ar+br)*sizeof(T)); pipe.InitBuffer(oq,1,32);
    pipe.InitBuffer(floats,(af+bf)*sizeof(float));
    pipe.InitBuffer(indices,2*kp*sizeof(int32_t));
    pipe.InitBuffer(packed,(N+1)*kp*sizeof(float));
    pipe.InitBuffer(prodBuf,(N*kp>M*8?N*kp:M*8)*sizeof(float));
    pipe.InitBuffer(values,(nr+8*M)*sizeof(float));
    auto fa=floats.Get<float>();auto fb=fa[af];
    auto bp=packed.Get<float>();auto av=bp[N*kp];auto prod=prodBuf.Get<float>();
    auto dots=values.Get<float>();auto rows=dots[nr];
    auto ia=indices.Get<int32_t>();auto ib=ia[kp];
    AscendC::CreateVecIndex(ia,int32_t(0),K);
    AscendC::CreateVecIndex(ib,int32_t(0),K);AscendC::PipeBarrier<PIPE_V>();
    AscendC::Muls(ia,ia,int32_t((TA?M:1)*sizeof(float)),K);
    AscendC::Muls(ib,ib,int32_t((TB?1:N)*sizeof(float)),K);
    AscendC::PipeBarrier<PIPE_V>();
    auto iau=ia.template ReinterpretCast<uint32_t>();auto ibu=ib.template ReinterpretCast<uint32_t>();
    AscendC::GlobalTensor<T> ga,gb;AscendC::GlobalTensor<float> gy;
    ga.SetGlobalBuffer(reinterpret_cast<__gm__ T*>(a),int64_t(B)*M*K);
    gb.SetGlobalBuffer(reinterpret_cast<__gm__ T*>(b),int64_t(B)*N*K);
    gy.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(y),B);
    for(int32_t batch=AscendC::GetBlockIdx();batch<B;batch+=workers){
        auto in=iq.AllocTensor<T>();
        AscendC::DataCopyPadExtParams<T> pad{false,0,0,T(0)};
        AscendC::DataCopyExtParams acp{1,uint32_t(M*K*sizeof(T)),0,0,0};
        AscendC::DataCopyExtParams bcp{1,uint32_t(N*K*sizeof(T)),0,0,0};
        AscendC::DataCopyPad(in,ga[int64_t(batch)*M*K],acp,pad);
        AscendC::DataCopyPad(in[ar],gb[int64_t(batch)*N*K],bcp,pad);
        iq.EnQue(in);in=iq.DeQue<T>();
        AscendC::Cast(fa,in,AscendC::RoundMode::CAST_NONE,M*K);
        AscendC::Cast(fb,in[ar],AscendC::RoundMode::CAST_NONE,N*K);
        AscendC::Duplicate(bp,0.0f,(N+1)*kp);
        AscendC::Duplicate(rows,0.0f,M*8);AscendC::PipeBarrier<PIPE_V>();
        for(int32_t n=0;n<N;++n)
            AscendC::Gather(bp[n*kp],fb,ibu,uint32_t((TB?n*K:n)*sizeof(float)),K);
        AscendC::PipeBarrier<PIPE_V>();
        const uint8_t stride=static_cast<uint8_t>(kp/8);
        const AscendC::BinaryRepeatParams mulp{1,1,1,stride,0,stride};
        for(int32_t m=0;m<M;++m){
            AscendC::Gather(av,fa,iau,uint32_t((TA?m:m*K)*sizeof(float)),K);
            AscendC::PipeBarrier<PIPE_V>();
            for(int32_t k=0;k<kp;k+=64)
                AscendC::Mul(prod[k],av[k],bp[k],MinI(kp,64),N,mulp);
            AscendC::PipeBarrier<PIPE_V>();
            if(kp==128){
                const AscendC::BinaryRepeatParams addp{1,1,1,16,16,16};
                AscendC::Add(prod,prod,prod[64],64,N,addp);
                AscendC::PipeBarrier<PIPE_V>();
            }
            AscendC::WholeReduceSum(dots,prod,MinI(kp,64),N,1,1,kp/8);
            AscendC::PipeBarrier<PIPE_V>();
            AscendC::WholeReduceMax(rows[m*8],dots,N,1,1,1,8,
                AscendC::ReduceOrder::ORDER_ONLY_VALUE);
            AscendC::PipeBarrier<PIPE_V>();
        }
        auto out=oq.AllocTensor<float>();
        AscendC::ReduceSum(out,rows,prod,M*8);
        oq.EnQue(out);out=oq.DeQue<float>();
        AscendC::DataCopyExtParams cp{1,sizeof(float),0,0,0};
        AscendC::DataCopyPad(gy[batch],out,cp);
        oq.FreeTensor(out);iq.FreeTensor(in);
    }
}

struct SkinnyPlan {int32_t B,L,K,kp,chunk,chunks,padded,workers,direct;};
// Finite-length max used only in the M=1 epilogue. No padding participates.
__aicore__ inline void FinishMax(const AscendC::LocalTensor<float>& out,
    const AscendC::LocalTensor<float>& src,const AscendC::LocalTensor<float>& tmp,int32_t n){
    AscendC::Duplicate(tmp,NEG_INF,136);AscendC::PipeBarrier<PIPE_V>();
    const int32_t full=n/64,tail=n%64;
    if(full) AscendC::WholeReduceMax(tmp,src,64,full,1,1,8,AscendC::ReduceOrder::ORDER_ONLY_VALUE);
    if(tail) AscendC::WholeReduceMax(tmp[128],src[full*64],tail,1,1,1,8,AscendC::ReduceOrder::ORDER_ONLY_VALUE);
    AscendC::PipeBarrier<PIPE_V>();
    AscendC::Max(tmp,tmp,tmp[64],64);AscendC::PipeBarrier<PIPE_V>();
    AscendC::WholeReduceMax(out,tmp,64,1,1,1,8,AscendC::ReduceOrder::ORDER_ONLY_VALUE);
    AscendC::PipeBarrier<PIPE_V>();AscendC::Max(out,out,tmp[128],1);
}
// Full-K contiguous dot bank. Unlike V5, supports every legal K up to 8192.
// Only selected when the BANK is stored [L,K]. Other layouts use the Cube path.
template<class T,bool SUM_ROWS>
__aicore__ inline void SkinnyDevice(GM_ADDR a,GM_ADDR b,GM_ADDR y,
    GM_ADDR partial,const SkinnyPlan& p){
    AscendC::TPipe pipe;
    const int32_t bankCap=p.chunk*p.kp>p.padded?p.chunk*p.kp:p.padded;
    int32_t scratchCap=p.kp>p.padded?p.kp:p.padded;
    if(scratchCap<136)scratchCap=136;
    AscendC::TQue<AscendC::TPosition::VECIN,1> iq;
    AscendC::TQue<AscendC::TPosition::VECOUT,1> dq,oq;
    AscendC::TBuf<AscendC::TPosition::VECCALC> vb,fb,sb,slots,indices;
    pipe.InitBuffer(iq,1,(p.kp+p.chunk*p.kp)*sizeof(T));
    pipe.InitBuffer(dq,1,((p.chunk+7)/8*8)*sizeof(float));pipe.InitBuffer(oq,1,32);
    pipe.InitBuffer(vb,p.kp*sizeof(float));pipe.InitBuffer(fb,bankCap*sizeof(float));
    pipe.InitBuffer(sb,scratchCap*sizeof(float));pipe.InitBuffer(slots,p.chunk*8*sizeof(float));
    pipe.InitBuffer(indices,((p.chunk+7)/8*8)*sizeof(int32_t));
    auto vec=vb.Get<float>();auto bank=fb.Get<float>();auto scratch=sb.Get<float>();
    auto sparse=slots.Get<float>();auto ix=indices.Get<int32_t>();
    AscendC::CreateVecIndex(ix,int32_t(0),p.chunk);AscendC::PipeBarrier<PIPE_V>();
    AscendC::Muls(ix,ix,int32_t(8*sizeof(float)),p.chunk);AscendC::PipeBarrier<PIPE_V>();
    auto uix=ix.template ReinterpretCast<uint32_t>();
    AscendC::GlobalTensor<T> gv,gb;AscendC::GlobalTensor<float> gp,gy;
    gv.SetGlobalBuffer(reinterpret_cast<__gm__ T*>(SUM_ROWS?b:a),int64_t(p.B)*p.K);
    gb.SetGlobalBuffer(reinterpret_cast<__gm__ T*>(SUM_ROWS?a:b),int64_t(p.B)*p.L*p.K);
    gp.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(partial),p.direct?0:int64_t(p.B)*p.padded);
    gy.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(y),p.B);
    const int32_t worker=AscendC::GetBlockIdx();int32_t lastBatch=-1;
    for(int32_t task=worker;task<p.B*p.chunks;task+=p.workers){
        const int32_t batch=task/p.chunks,l0=(task%p.chunks)*p.chunk;
        const int32_t live=MinI(p.chunk,p.L-l0);
        auto in=iq.AllocTensor<T>();
        AscendC::DataCopyPadExtParams<T> pad{true,0,static_cast<uint8_t>(p.kp-p.K),T(0)};
        AscendC::DataCopyExtParams cp{1,uint32_t(p.K*sizeof(T)),0,0,0};
        if(batch!=lastBatch)AscendC::DataCopyPad(in,gv[int64_t(batch)*p.K],cp,pad);
        cp.blockCount=static_cast<uint16_t>(live);
        AscendC::DataCopyPad(in[p.kp],gb[(int64_t(batch)*p.L+l0)*p.K],cp,pad);
        iq.EnQue(in);in=iq.DeQue<T>();
        if(batch!=lastBatch){AscendC::Cast(vec,in,AscendC::RoundMode::CAST_NONE,p.kp);lastBatch=batch;}
        AscendC::Cast(bank,in[p.kp],AscendC::RoundMode::CAST_NONE,live*p.kp);
        AscendC::PipeBarrier<PIPE_V>();
        for(int32_t r=0;r<live;++r){
            AscendC::Mul(bank[r*p.kp],bank[r*p.kp],vec,p.K);AscendC::PipeBarrier<PIPE_V>();
            AscendC::ReduceSum(sparse[r*8],bank[r*p.kp],scratch,p.K);
            AscendC::PipeBarrier<PIPE_V>();
        }
        auto dots=dq.AllocTensor<float>();AscendC::Gather(dots,sparse,uix,0,live);
        AscendC::PipeBarrier<PIPE_V>();
        if(p.direct){
            auto out=oq.AllocTensor<float>();
            if constexpr(SUM_ROWS)AscendC::ReduceSum(out,dots,scratch,live);
            else AscendC::WholeReduceMax(out,dots,live,1,1,1,8,AscendC::ReduceOrder::ORDER_ONLY_VALUE);
            oq.EnQue(out);out=oq.DeQue<float>();
            AscendC::DataCopyExtParams ocp{1,sizeof(float),0,0,0};
            AscendC::DataCopyPad(gy[batch],out,ocp);oq.FreeTensor(out);
            AscendC::PipeBarrier<PIPE_V>();
        }else{
            dq.EnQue(dots);dots=dq.DeQue<float>();
            AscendC::DataCopyExtParams ocp{1,uint32_t(live*sizeof(float)),0,0,0};
            AscendC::DataCopyPad(gp[int64_t(batch)*p.padded+l0],dots,ocp);
        }
        dq.FreeTensor(dots);iq.FreeTensor(in);
    }
    if(p.direct)return;
    Fence<AscendC::HardEvent::MTE3_MTE2>(pipe);AscendC::SyncAll<true>();
    for(int32_t batch=worker;batch<p.B;batch+=p.workers){
        AscendC::DataCopyExtParams cp{1,uint32_t(p.L*sizeof(float)),0,0,0};
        AscendC::DataCopyPadExtParams<float> np{false,0,0,0.0f};
        AscendC::DataCopyPad(bank,gp[int64_t(batch)*p.padded],cp,np);
        Fence<AscendC::HardEvent::MTE2_V>(pipe);
        auto out=oq.AllocTensor<float>();
        if constexpr(SUM_ROWS)AscendC::ReduceSum(out,bank,scratch,p.L);
        else FinishMax(out,bank,scratch,p.L);
        oq.EnQue(out);out=oq.DeQue<float>();
        AscendC::DataCopyExtParams ocp{1,sizeof(float),0,0,0};
        AscendC::DataCopyPad(gy[batch],out,ocp);oq.FreeTensor(out);
        Fence<AscendC::HardEvent::V_MTE2>(pipe);
    }
}


// BMMS71_ROUTE_BEGIN
static inline int32_t Up(int32_t x,int32_t y){return (x+y-1)/y;}
static inline int32_t MinH(int32_t a,int32_t b){return a<b?a:b;}
static inline int32_t Pow2Up(int32_t x,int32_t limit){int32_t r=16;while(r<x&&r<limit)r*=2;return r;}
static inline bool UseTiny(int32_t M,int32_t N,int32_t K){return int64_t(M)*N<=16&&K<=1024&&int64_t(M)*N*K<=8192;}
static inline bool UseResident(int32_t M,int32_t N,int32_t K){
    return M<=32&&N<=64&&K<=128&&int64_t(M)*N<=256&&int64_t(M)*N*K<=16384&&int64_t(M+N)*K<=8192;
}
static inline bool UseSkinny(int32_t M,int32_t N,bool ta,bool tb){
    return (N==1&&!ta)||(M==1&&tb);
}
static inline SkinnyPlan MakeSkinny(int32_t B,int32_t L,int32_t K,int32_t cores){
    SkinnyPlan p{};p.B=B;p.L=L;p.K=K;p.kp=Up(K,16)*16;
    p.chunk=MinH(16,8192/p.kp);p.chunks=Up(L,p.chunk);
    p.padded=Up(L,16)*16;p.workers=MinH(cores*2,B*p.chunks);p.direct=p.chunks==1;return p;
}

enum class Family : int32_t { Dot=0, Tiny=1, Resident=2, Skinny=3, Generic43=4 };
static inline Family SelectFamily(int32_t M,int32_t N,int32_t K,bool ta,bool tb)
{
    if (M==1 && N==1) return Family::Dot;
    if (UseTiny(M,N,K)) return Family::Tiny;
    if (UseResident(M,N,K)) return Family::Resident;
    if (UseSkinny(M,N,ta,tb)) return Family::Skinny;
    return Family::Generic43;
}
// BMMS71_ROUTE_END
} // namespace bmms71

namespace bmms8 {inline int CeilDivI(int x,int y){return (x+y-1)/y;}
__aicore__ inline void PairAccumulate(
    const AscendC::LocalTensor<float>& hi,const AscendC::LocalTensor<float>& lo,
    const AscendC::LocalTensor<float>& x,const AscendC::LocalTensor<float>& sum,
    const AscendC::LocalTensor<float>& bp,const AscendC::LocalTensor<float>& err,int32_t n){
    AscendC::Add(sum,hi,x,n);AscendC::PipeBarrier<PIPE_V>();
    AscendC::Sub(bp,sum,hi,n);AscendC::PipeBarrier<PIPE_V>();
    AscendC::Sub(err,sum,bp,n);AscendC::PipeBarrier<PIPE_V>();
    AscendC::Sub(err,hi,err,n);
    AscendC::Sub(bp,x,bp,n);AscendC::PipeBarrier<PIPE_V>();
    AscendC::Add(err,err,bp,n);AscendC::PipeBarrier<PIPE_V>();
    AscendC::Add(lo,lo,err,n);
    AscendC::Add(hi,hi,x,n);AscendC::PipeBarrier<PIPE_V>();
}

// Fixed, alignment-aware reduction of FP32 high/low pairs. Full K has already
// been evaluated for every row. Only the final round converts the pair to y.
__aicore__ inline void FinishPairSum(
    const AscendC::LocalTensor<float>& out,const AscendC::LocalTensor<float>& hi,
    const AscendC::LocalTensor<float>& lo,const AscendC::LocalTensor<float>& sum,
    const AscendC::LocalTensor<float>& bp,const AscendC::LocalTensor<float>& err,
    int32_t n,AscendC::TPipe& pipe){
    while(n>8){
        const int32_t split=CeilDivI(CeilDivI(n,2),8)*8;
        const int32_t pairs=n-split;
        PairAccumulate(hi,lo,hi[split],sum,bp,err,pairs);
        AscendC::Add(lo,lo,lo[split],pairs);AscendC::PipeBarrier<PIPE_V>();
        n=split;
    }
    bmms71::Fence<AscendC::HardEvent::V_S>(pipe);
    float h=0.0f,l=0.0f;
    for(int32_t i=0;i<n;++i){
        const float x=hi.GetValue(i),t=h+x,b=t-h;
        const float e=(h-(t-b))+(x-b);
        l=l+e; l=l+lo.GetValue(i); h=t;
    }
    out.SetValue(0,h+l);
    // The result was written by Scalar; the queue's normal V->MTE3 dependency
    // must not be used without connecting Scalar to Vector first.
    bmms71::Fence<AscendC::HardEvent::S_V>(pipe);
}

}
namespace bmms83 {
constexpr int32_t TM=64, TN=128, AM=256, BN=512, KB=32, LC=64;
constexpr int32_t M_STAGE_TILES=AM/TM;
constexpr uint16_t READY=4, FREE=6;
__aicore__ inline int32_t MinI(int32_t a,int32_t b){return a<b?a:b;}
static inline int32_t UpH(int32_t a,int32_t b){return (a+b-1)/b;}
static inline int32_t MinH(int32_t a,int32_t b){return a<b?a:b;}
static inline int32_t MaxH(int32_t a,int32_t b){return a>b?a:b;}

struct NativePlan {
    int32_t B,M,N,K;
    int32_t mTiles,nTiles;
    int32_t pM,pN;
    int32_t tasks,blocks;
};

static inline bool NativeEligible(int32_t M,int32_t N,int32_t K){
    return M>=16&&N>=16&&M%16==0&&N%16==0&&(K==32||K==64||K==128);
}

// Number of AM-sized A stages generated after partitioning mTiles into pM
// contiguous shards.  Each such stage re-reads its corresponding B shard.
static inline int32_t MStageCount(int32_t mTiles,int32_t pM){
    const int32_t q=mTiles/pM,r=mTiles-q*pM;
    const int32_t hi=UpH(q+1,M_STAGE_TILES),lo=q?UpH(q,M_STAGE_TILES):0;
    return r*hi+(pM-r)*lo;
}

// Lightweight host-side shape cost.  The dominant term estimates the largest
// per-wave Cube-tile workload.  Secondary terms charge A re-reads caused by pN,
// B re-reads caused by AM staging / pM boundaries, row-partial traffic when pN>1,
// and excessive task count.  It intentionally contains no hidden case IDs.
static inline double NativeCost(int32_t B,int32_t M,int32_t N,int32_t K,
    int32_t mTiles,int32_t nTiles,int32_t pM,int32_t pN,int32_t cores){
    const int32_t tasks=B*pM*pN;
    const int32_t waves=UpH(tasks,cores);
    const int32_t mt=UpH(mTiles,pM),nt=UpH(nTiles,pN);
    const double cube=double(mt)*double(nt)*double(waves);
    const int32_t mStages=MStageCount(mTiles,pM);
    const double input=(double(M)*double(pN)+double(N)*double(mStages))/double(TM*TN);
    const double partial=(pN==1)?(0.015*double(pM)):
        (0.40*double(M)*double(pN)/double(TM*TN));
    const double taskTax=0.015*double(tasks)/double(MaxH(1,MinH(tasks,cores)));
    // Small K is relatively more sensitive to fixed ring/vector overhead, so
    // keep the scheduler slightly more conservative about N splitting at K=32.
    const double nSplitTax=(pN<=1)?0.0:(K==32?0.08:K==64?0.04:0.02)*double(pN-1);
    return cube+0.55*input+partial+taskTax+nSplitTax;
}

static inline NativePlan MakeNative(int32_t B,int32_t M,int32_t N,int32_t K,int32_t cores){
    NativePlan best{};best.B=B;best.M=M;best.N=N;best.K=K;
    best.mTiles=UpH(M,TM);best.nTiles=UpH(N,TN);
    best.pM=1;best.pN=1;best.tasks=B;best.blocks=MinH(cores,B);
    double bestCost=NativeCost(B,M,N,K,best.mTiles,best.nTiles,1,1,cores);

    // At most ~2 waves are considered. More waves normally duplicate input
    // traffic without adding occupancy, while one extra wave can improve a
    // badly indivisible tile grid (for example 3 batches on 20 groups).
    const int32_t perBatchNeed=MaxH(1,UpH(cores,B));
    const int32_t splitCap=MinH(cores,2*perBatchNeed);
    const int32_t maxPM=MinH(best.mTiles,splitCap);
    const int32_t maxPN=MinH(best.nTiles,splitCap);
    for(int32_t pm=1;pm<=maxPM;++pm){
        for(int32_t pn=1;pn<=maxPN;++pn){
            const int32_t tasks=B*pm*pn;
            if(tasks>2*cores)continue;
            const double c=NativeCost(B,M,N,K,best.mTiles,best.nTiles,pm,pn,cores);
            // Stable tie-breaks: less N splitting, then fewer total tasks.
            if(c<bestCost-1e-9 ||
               ((c<=bestCost+1e-9)&&(pn<best.pN || (pn==best.pN&&tasks<best.tasks)))){
                bestCost=c;best.pM=pm;best.pN=pn;best.tasks=tasks;
                best.blocks=MinH(cores,tasks);
            }
        }
    }
    return best;
}

constexpr int32_t PACKET_TILES=4;
static inline uint64_t NativeRingBytes(const NativePlan& p){
    return uint64_t(p.blocks)*2*PACKET_TILES*TM*TN*4;
}
static inline uint64_t NativePartialBytes(const NativePlan& p){
    // Probe P01: always materialize row maxima [B][pN][M].
    return uint64_t(p.B)*p.pN*p.M*4ULL;
}

template<class T,bool TA,bool TB,int TK>
class SmallKProducer {
    AscendC::TPipe* pipe_; NativePlan p;
    AscendC::GlobalTensor<T> a,b;AscendC::GlobalTensor<float> ring;
    AscendC::TBuf<AscendC::TPosition::A1> a1Buf;
    AscendC::TBuf<AscendC::TPosition::B1> b1Buf;
    AscendC::TBuf<AscendC::TPosition::A2> a2Buf;
    AscendC::TBuf<AscendC::TPosition::B2> b2Buf;
    AscendC::TBuf<AscendC::TPosition::CO1> cBuf;
    int32_t seq=0;
    AscendC::TEventID bReady[3],bFree[3],abReady[2],abFree[2],cReady[2],cFree[2];

    __aicore__ inline void LoadA(int batch,int m0,int mr){
        auto dst=a1Buf.template Get<T>();AscendC::Nd2NzParams q{};q.ndNum=1;
        q.nValue=TA?TK:mr;q.dValue=TA?mr:TK;q.srcDValue=TA?p.M:TK;
        q.dstNzC0Stride=TA?TK:mr;q.dstNzNStride=1;
        const int64_t off=int64_t(batch)*p.M*TK+(TA?m0:int64_t(m0)*TK);
        AscendC::DataCopy(dst,a[off],q);
        AscendC::SetFlag<AscendC::HardEvent::MTE2_MTE1>(bReady[2]);
        AscendC::WaitFlag<AscendC::HardEvent::MTE2_MTE1>(bReady[2]);
    }
    __aicore__ inline void LoadB(int batch,int n0,int nr,int stage){
        auto dst=b1Buf.template Get<T>()[stage*TK*BN];AscendC::Nd2NzParams q{};q.ndNum=1;
        q.nValue=TB?nr:TK;q.dValue=TB?TK:nr;q.srcDValue=TB?TK:p.N;
        q.dstNzC0Stride=TB?nr:TK;q.dstNzNStride=1;
        const int64_t off=int64_t(batch)*TK*p.N+(TB?int64_t(n0)*TK:n0);
        AscendC::DataCopy(dst,b[off],q);
        AscendC::SetFlag<AscendC::HardEvent::MTE2_MTE1>(bReady[stage]);
    }
    __aicore__ inline void LoadL0(int mo,int no,int mr,int nr,int ar,int br,int stage,int slot){
        auto srcA=a1Buf.template Get<T>();auto srcB=b1Buf.template Get<T>()[stage*TK*BN];
        auto dstA=a2Buf.template Get<T>()[slot*TM*TK];auto dstB=b2Buf.template Get<T>()[slot*TK*TN];
        AscendC::LoadData2DParams la{};la.repeatTimes=TK/16;
        la.srcStride=TA?1:ar/16;la.ifTranspose=TA;
        for(int i=0;i<mr/16;++i){
            const int off=TA?(mo/16+i)*TK*16:(mo/16+i)*256;
            AscendC::LoadData(dstA[i*TK*16],srcA[off],la);
        }
        AscendC::LoadData2DParams lb{};lb.repeatTimes=nr/16;
        lb.srcStride=TB?1:TK/16;lb.ifTranspose=!TB;
        for(int j=0;j<TK/16;++j){
            const int off=TB?j*br*16+(no/16)*256:(no/16)*TK*16+j*256;
            AscendC::LoadData(dstB[j*nr*16],srcB[off],lb);
        }
        AscendC::SetFlag<AscendC::HardEvent::MTE1_M>(abReady[slot]);
        AscendC::WaitFlag<AscendC::HardEvent::MTE1_M>(abReady[slot]);
    }
    __aicore__ inline void Emit(int group,int mo,int no,int mr,int nr,int ar,int br,int stage){
        const int slot=seq&1;
        if(seq>=2){
            AscendC::WaitFlag<AscendC::HardEvent::M_MTE1>(abFree[slot]);
            AscendC::WaitFlag<AscendC::HardEvent::FIX_M>(cFree[slot]);
        }
        LoadL0(mo,no,mr,nr,ar,br,stage,slot);
        auto aa=a2Buf.template Get<T>()[slot*TM*TK];auto bb=b2Buf.template Get<T>()[slot*TK*TN];
        auto cc=cBuf.template Get<float>()[slot*TM*TN];
        AscendC::MmadParams q{};q.m=mr;q.n=nr;q.k=TK;q.cmatrixInitVal=true;
        AscendC::Mmad(cc,aa,bb,q);
        AscendC::SetFlag<AscendC::HardEvent::M_MTE1>(abFree[slot]);
        AscendC::SetFlag<AscendC::HardEvent::M_FIX>(cReady[slot]);
        AscendC::WaitFlag<AscendC::HardEvent::M_FIX>(cReady[slot]);
        const int packet=seq/PACKET_TILES,packetSlot=packet&1,tileSlot=seq%PACKET_TILES;
        // Reserve the whole GM packet before its first Fixpipe; L0C still has two independent slots.
        if(tileSlot==0&&packet>=2)AscendC::CrossCoreWaitFlag<0x2>(FREE+packetSlot);
        AscendC::FixpipeParamsV220 f{};f.nSize=nr;f.mSize=mr;f.srcStride=mr;
        f.dstStride=TN;f.ndNum=1;f.quantPre=QuantMode_t::NoQuant;
        AscendC::Fixpipe<float,float>(ring[((int64_t(group)*2+packetSlot)*PACKET_TILES+tileSlot)*TM*TN],cc,f);
        AscendC::SetFlag<AscendC::HardEvent::FIX_M>(cFree[slot]);
        if(tileSlot+1==PACKET_TILES)AscendC::CrossCoreSetFlag<0x2,PIPE_FIX>(READY+packetSlot);
        ++seq;
    }
public:
    __aicore__ inline void Init(GM_ADDR x,GM_ADDR z,GM_ADDR r,const NativePlan& plan,AscendC::TPipe* pipe){
        p=plan;pipe_=pipe;
        for(int i=0;i<3;++i){
            bReady[i]=pipe_->AllocEventID<AscendC::HardEvent::MTE2_MTE1>();
            bFree[i]=pipe_->AllocEventID<AscendC::HardEvent::MTE1_MTE2>();
        }
        for(int i=0;i<2;++i){
            abReady[i]=pipe_->AllocEventID<AscendC::HardEvent::MTE1_M>();
            abFree[i]=pipe_->AllocEventID<AscendC::HardEvent::M_MTE1>();
            cReady[i]=pipe_->AllocEventID<AscendC::HardEvent::M_FIX>();
            cFree[i]=pipe_->AllocEventID<AscendC::HardEvent::FIX_M>();
        }
        a.SetGlobalBuffer(reinterpret_cast<__gm__ T*>(x),int64_t(p.B)*p.M*TK);
        b.SetGlobalBuffer(reinterpret_cast<__gm__ T*>(z),int64_t(p.B)*TK*p.N);
        ring.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(r),int64_t(p.blocks)*2*PACKET_TILES*TM*TN);
        pipe->InitBuffer(a1Buf,AM*TK*sizeof(T));pipe->InitBuffer(b1Buf,2*TK*BN*sizeof(T));
        pipe->InitBuffer(a2Buf,2*TM*TK*sizeof(T));pipe->InitBuffer(b2Buf,2*TK*TN*sizeof(T));
        pipe->InitBuffer(cBuf,2*TM*TN*sizeof(float));
    }
    __aicore__ inline void Process(){
        const int group=AscendC::GetBlockIdx();
        const int perBatch=p.pM*p.pN;
        for(int task=group;task<p.tasks;task+=p.blocks){
            const int batch=task/perBatch,slot=task-batch*perBatch;
            const int ms=slot/p.pN,ns=slot-ms*p.pN;
            const int mt0=ms*p.mTiles/p.pM,mt1=(ms+1)*p.mTiles/p.pM;
            const int nt0=ns*p.nTiles/p.pN,nt1=(ns+1)*p.nTiles/p.pN;
            const int mBegin=mt0*TM,mEnd=MinI(mt1*TM,p.M);
            const int nBegin=nt0*TN,nEnd=MinI(nt1*TN,p.N);

            for(int mBase=mBegin;mBase<mEnd;mBase+=AM){
                const int ar=MinI(AM,mEnd-mBase);
                LoadA(batch,mBase,ar);
                LoadB(batch,nBegin,MinI(BN,nEnd-nBegin),0);
                int localPanel=0;
                for(int nBase=nBegin;nBase<nEnd;nBase+=BN,++localPanel){
                    const int stage=localPanel&1,br=MinI(BN,nEnd-nBase);
                    AscendC::WaitFlag<AscendC::HardEvent::MTE2_MTE1>(bReady[stage]);
                    if(nBase+BN<nEnd){
                        const int next=stage^1;
                        if(localPanel>=1)AscendC::WaitFlag<AscendC::HardEvent::MTE1_MTE2>(bFree[next]);
                        LoadB(batch,nBase+BN,MinI(BN,nEnd-(nBase+BN)),next);
                    }
                    for(int mo=0;mo<ar;mo+=TM){
                        for(int no=0;no<br;no+=TN){
                            Emit(group,mo,no,MinI(TM,ar-mo),MinI(TN,br-no),ar,br,stage);
                        }
                    }
                    AscendC::SetFlag<AscendC::HardEvent::MTE1_MTE2>(bFree[stage]);
                }
                const int panelCount=(nEnd-nBegin+BN-1)/BN,used=MinI(2,panelCount);
                for(int st=0;st<used;++st)AscendC::WaitFlag<AscendC::HardEvent::MTE1_MTE2>(bFree[st]);
                AscendC::SetFlag<AscendC::HardEvent::MTE1_MTE2>(bFree[2]);
                AscendC::WaitFlag<AscendC::HardEvent::MTE1_MTE2>(bFree[2]);
            }
        }
        // Publish an incomplete last packet before waiting for any final FREE.
        if(seq%PACKET_TILES)AscendC::CrossCoreSetFlag<0x2,PIPE_FIX>(READY+((seq/PACKET_TILES)&1));
        const int packets=(seq+PACKET_TILES-1)/PACKET_TILES;
        for(int s=0;s<MinI(2,packets);++s)AscendC::CrossCoreWaitFlag<0x2>(FREE+s);
        for(int s=0;s<MinI(2,seq);++s){
            AscendC::WaitFlag<AscendC::HardEvent::M_MTE1>(abFree[s]);
            AscendC::WaitFlag<AscendC::HardEvent::FIX_M>(cFree[s]);
        }
        for(int i=0;i<3;++i){
            pipe_->ReleaseEventID<AscendC::HardEvent::MTE2_MTE1>(bReady[i]);
            pipe_->ReleaseEventID<AscendC::HardEvent::MTE1_MTE2>(bFree[i]);
        }
        for(int i=0;i<2;++i){
            pipe_->ReleaseEventID<AscendC::HardEvent::MTE1_M>(abReady[i]);
            pipe_->ReleaseEventID<AscendC::HardEvent::M_MTE1>(abFree[i]);
            pipe_->ReleaseEventID<AscendC::HardEvent::M_FIX>(cReady[i]);
            pipe_->ReleaseEventID<AscendC::HardEvent::FIX_M>(cFree[i]);
        }
    }
};

class SmallKConsumer {
    NativePlan p;AscendC::TPipe* pipe_;
    AscendC::GlobalTensor<float> ring,part,out;
    AscendC::TQue<AscendC::TPosition::VECIN,1> cq;
    AscendC::TQue<AscendC::TPosition::VECOUT,1> oq;
    AscendC::TBuf<AscendC::TPosition::VECCALC> groupBuf,rowBuf,sumBuf;
    AscendC::TBuf<AscendC::TPosition::VECOUT> runningBuf;
    AscendC::TBuf<AscendC::TPosition::VECIN> mergedBuf,tmpBuf;
public:
    __aicore__ inline void Init(GM_ADDR r,GM_ADDR pt,GM_ADDR y,const NativePlan& plan,AscendC::TPipe* pipe){
        p=plan;pipe_=pipe;
        ring.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(r),int64_t(p.blocks)*2*TM*TN);
        part.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(pt),int64_t(p.B)*p.pN*p.M);
        out.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(y),p.B);
        pipe->InitBuffer(cq,1,(TM/2)*TN*4);pipe->InitBuffer(oq,1,32);
        pipe->InitBuffer(groupBuf,(TM/2)*TN*4);pipe->InitBuffer(rowBuf,(TM/2)*4);
        pipe->InitBuffer(runningBuf,AM*4);pipe->InitBuffer(mergedBuf,p.M*4);
        pipe->InitBuffer(tmpBuf,p.M*4);pipe->InitBuffer(sumBuf,p.M*4);
    }
    __aicore__ inline void Process(){
        const int worker=AscendC::GetBlockIdx(),group=worker/2,sub=worker%2;
        const int perBatch=p.pM*p.pN;
        int seq=0;auto acc=groupBuf.Get<float>();auto rows=rowBuf.Get<float>();auto run=runningBuf.Get<float>();
        for(int task=group;task<p.tasks;task+=p.blocks){
            const int batch=task/perBatch,slot=task-batch*perBatch;
            const int ms=slot/p.pN,ns=slot-ms*p.pN;
            const int mt0=ms*p.mTiles/p.pM,mt1=(ms+1)*p.mTiles/p.pM;
            const int nt0=ns*p.nTiles/p.pN,nt1=(ns+1)*p.nTiles/p.pN;
            const int mBegin=mt0*TM,mEnd=MinI(mt1*TM,p.M);
            const int nBegin=nt0*TN,nEnd=MinI(nt1*TN,p.N);
            for(int mBase=mBegin;mBase<mEnd;mBase+=AM){
                const int ar=MinI(AM,mEnd-mBase);
                AscendC::Duplicate(run,bmmmaxsum_v43::NEG_INF,ar);AscendC::PipeBarrier<PIPE_V>();
                for(int nBase=nBegin;nBase<nEnd;nBase+=BN){
                    const int br=MinI(BN,nEnd-nBase);
                    for(int mo=0;mo<ar;mo+=TM){
                        const int mr=MinI(TM,ar-mo),vr=mr/2;
                        AscendC::Duplicate(acc,bmmmaxsum_v43::NEG_INF,vr*TN);AscendC::PipeBarrier<PIPE_V>();
                        for(int no=0;no<br;no+=TN){
                            const int nr=MinI(TN,br-no),ringSlot=seq&1;
                            AscendC::CrossCoreWaitFlag<0x2>(READY+ringSlot);
                            auto c=cq.AllocTensor<float>();
                            AscendC::Duplicate(c,bmmmaxsum_v43::NEG_INF,vr*TN);
                            bmms71::Fence<AscendC::HardEvent::V_MTE2>(*pipe_);
                            const int64_t off=(int64_t(group)*2+ringSlot)*TM*TN+sub*vr*TN;
                            AscendC::DataCopyExtParams cp{static_cast<uint16_t>(vr),uint32_t(nr*4),uint32_t((TN-nr)*4),uint32_t((TN-nr)/8),0};
                            AscendC::DataCopyPadExtParams<float> pd{false,0,0,0.0f};
                            AscendC::DataCopyPad(c,ring[off],cp,pd);cq.EnQue(c);c=cq.DeQue<float>();
                            AscendC::CrossCoreSetFlag<0x2,PIPE_MTE2>(FREE+ringSlot);
                            AscendC::Max(acc,acc,c,vr*TN);AscendC::PipeBarrier<PIPE_V>();cq.FreeTensor(c);++seq;
                        }
                        AscendC::BinaryRepeatParams rp{1,1,1,16,16,16};
                        AscendC::Max(acc,acc,acc[64],64,vr,rp);AscendC::PipeBarrier<PIPE_V>();
                        AscendC::WholeReduceMax(rows,acc,64,vr,1,1,16,AscendC::ReduceOrder::ORDER_ONLY_VALUE);
                        AscendC::PipeBarrier<PIPE_V>();
                        AscendC::Max(run[mo+sub*vr],run[mo+sub*vr],rows,vr);AscendC::PipeBarrier<PIPE_V>();
                    }
                }
                bmms71::Fence<AscendC::HardEvent::V_MTE3>(*pipe_);
                for(int mo=0;mo<ar;mo+=TM){
                    const int vr=MinI(TM,ar-mo)/2;
                    const int64_t dst=(int64_t(batch)*p.pN+ns)*p.M+mBase+mo+sub*vr;
                    AscendC::DataCopy(part[dst],run[mo+sub*vr],vr);
                }
                bmms71::Fence<AscendC::HardEvent::MTE3_V>(*pipe_);
            }
        }
        bmms71::Fence<AscendC::HardEvent::MTE3_MTE2>(*pipe_);AscendC::SyncAll<true>();
        auto merged=mergedBuf.Get<float>(),tmp=tmpBuf.Get<float>();
        for(int batch=worker;batch<p.B;batch+=2*p.blocks){
            const int64_t start=int64_t(batch)*p.pN*p.M;
            AscendC::DataCopy(merged,part[start],p.M);bmms71::Fence<AscendC::HardEvent::MTE2_V>(*pipe_);
            for(int ns=1;ns<p.pN;++ns){
                AscendC::DataCopy(tmp,part[start+int64_t(ns)*p.M],p.M);bmms71::Fence<AscendC::HardEvent::MTE2_V>(*pipe_);
                AscendC::Max(merged,merged,tmp,p.M);bmms71::Fence<AscendC::HardEvent::V_MTE2>(*pipe_);
            }
            auto yy=oq.AllocTensor<float>();AscendC::ReduceSum(yy,merged,sumBuf.Get<float>(),p.M);
            oq.EnQue(yy);yy=oq.DeQue<float>();AscendC::DataCopyExtParams oc{1,4,0,0,0};
            AscendC::DataCopyPad(out[batch],yy,oc);oq.FreeTensor(yy);bmms71::Fence<AscendC::HardEvent::V_MTE2>(*pipe_);
        }
    }
};

class SmallKPacketConsumer {
    NativePlan p;AscendC::TPipe* pipe_;
    AscendC::GlobalTensor<float> ring,part,out;
    AscendC::TQue<AscendC::TPosition::VECIN,1> cq;
    AscendC::TQue<AscendC::TPosition::VECOUT,1> oq;
    AscendC::TBuf<AscendC::TPosition::VECCALC> groupBuf,rowBuf,sumBuf;
    AscendC::TBuf<AscendC::TPosition::VECOUT> runningBuf;
    AscendC::TBuf<AscendC::TPosition::VECIN> mergedBuf,tmpBuf;
public:
    __aicore__ inline void Init(GM_ADDR r,GM_ADDR pt,GM_ADDR y,const NativePlan& plan,AscendC::TPipe* pipe){
        p=plan;pipe_=pipe;
        ring.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(r),int64_t(p.blocks)*2*PACKET_TILES*TM*TN);
        part.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(pt),int64_t(p.B)*p.pN*p.M);
        out.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(y),p.B);
        pipe->InitBuffer(cq,1,(TM/2)*TN*4);pipe->InitBuffer(oq,1,32);
        pipe->InitBuffer(groupBuf,(TM/2)*TN*4);pipe->InitBuffer(rowBuf,(TM/2)*4);
        pipe->InitBuffer(runningBuf,AM*4);pipe->InitBuffer(mergedBuf,p.M*4);
        pipe->InitBuffer(tmpBuf,p.M*4);pipe->InitBuffer(sumBuf,p.M*4);
    }
    __aicore__ inline void Process(){
        const int worker=AscendC::GetBlockIdx(),group=worker/2,sub=worker%2;
        const int perBatch=p.pM*p.pN;
        int seq=0;auto acc=groupBuf.Get<float>();auto rows=rowBuf.Get<float>();auto run=runningBuf.Get<float>();
        for(int task=group;task<p.tasks;task+=p.blocks){
            const int batch=task/perBatch,slot=task-batch*perBatch;
            const int ms=slot/p.pN,ns=slot-ms*p.pN;
            const int mt0=ms*p.mTiles/p.pM,mt1=(ms+1)*p.mTiles/p.pM;
            const int nt0=ns*p.nTiles/p.pN,nt1=(ns+1)*p.nTiles/p.pN;
            const int mBegin=mt0*TM,mEnd=MinI(mt1*TM,p.M);
            const int nBegin=nt0*TN,nEnd=MinI(nt1*TN,p.N);
            for(int mBase=mBegin;mBase<mEnd;mBase+=AM){
                const int ar=MinI(AM,mEnd-mBase);
                AscendC::Duplicate(run,bmmmaxsum_v43::NEG_INF,ar);AscendC::PipeBarrier<PIPE_V>();
                for(int nBase=nBegin;nBase<nEnd;nBase+=BN){
                    const int br=MinI(BN,nEnd-nBase);
                    for(int mo=0;mo<ar;mo+=TM){
                        const int mr=MinI(TM,ar-mo),vr=mr/2;
                        AscendC::Duplicate(acc,bmmmaxsum_v43::NEG_INF,vr*TN);AscendC::PipeBarrier<PIPE_V>();
                        for(int no=0;no<br;no+=TN){
                            const int nr=MinI(TN,br-no),ringSlot=(seq/PACKET_TILES)&1,tileSlot=seq%PACKET_TILES;
                            if(tileSlot==0)AscendC::CrossCoreWaitFlag<0x2>(READY+ringSlot);
                            auto c=cq.AllocTensor<float>();
                            AscendC::Duplicate(c,bmmmaxsum_v43::NEG_INF,vr*TN);
                            bmms71::Fence<AscendC::HardEvent::V_MTE2>(*pipe_);
                            const int64_t off=((int64_t(group)*2+ringSlot)*PACKET_TILES+tileSlot)*TM*TN+sub*vr*TN;
                            AscendC::DataCopyExtParams cp{static_cast<uint16_t>(vr),uint32_t(nr*4),uint32_t((TN-nr)*4),uint32_t((TN-nr)/8),0};
                            AscendC::DataCopyPadExtParams<float> pd{false,0,0,0.0f};
                            AscendC::DataCopyPad(c,ring[off],cp,pd);cq.EnQue(c);c=cq.DeQue<float>();
                            if(tileSlot+1==PACKET_TILES)AscendC::CrossCoreSetFlag<0x2,PIPE_MTE2>(FREE+ringSlot);
                            AscendC::Max(acc,acc,c,vr*TN);AscendC::PipeBarrier<PIPE_V>();cq.FreeTensor(c);++seq;
                        }
                        AscendC::BinaryRepeatParams rp{1,1,1,16,16,16};
                        AscendC::Max(acc,acc,acc[64],64,vr,rp);AscendC::PipeBarrier<PIPE_V>();
                        AscendC::WholeReduceMax(rows,acc,64,vr,1,1,16,AscendC::ReduceOrder::ORDER_ONLY_VALUE);
                        AscendC::PipeBarrier<PIPE_V>();
                        AscendC::Max(run[mo+sub*vr],run[mo+sub*vr],rows,vr);AscendC::PipeBarrier<PIPE_V>();
                    }
                }
                bmms71::Fence<AscendC::HardEvent::V_MTE3>(*pipe_);
                for(int mo=0;mo<ar;mo+=TM){
                    const int vr=MinI(TM,ar-mo)/2;
                    const int64_t dst=(int64_t(batch)*p.pN+ns)*p.M+mBase+mo+sub*vr;
                    AscendC::DataCopy(part[dst],run[mo+sub*vr],vr);
                }
                bmms71::Fence<AscendC::HardEvent::MTE3_V>(*pipe_);
            }
        }
        // The final partial packet has no next tile to trigger the normal release.
        if(seq%PACKET_TILES)AscendC::CrossCoreSetFlag<0x2,PIPE_MTE2>(FREE+((seq/PACKET_TILES)&1));
        bmms71::Fence<AscendC::HardEvent::MTE3_MTE2>(*pipe_);AscendC::SyncAll<true>();
        auto merged=mergedBuf.Get<float>(),tmp=tmpBuf.Get<float>();
        for(int batch=worker;batch<p.B;batch+=2*p.blocks){
            const int64_t start=int64_t(batch)*p.pN*p.M;
            AscendC::DataCopy(merged,part[start],p.M);bmms71::Fence<AscendC::HardEvent::MTE2_V>(*pipe_);
            for(int ns=1;ns<p.pN;++ns){
                AscendC::DataCopy(tmp,part[start+int64_t(ns)*p.M],p.M);bmms71::Fence<AscendC::HardEvent::MTE2_V>(*pipe_);
                AscendC::Max(merged,merged,tmp,p.M);bmms71::Fence<AscendC::HardEvent::V_MTE2>(*pipe_);
            }
            auto yy=oq.AllocTensor<float>();AscendC::ReduceSum(yy,merged,sumBuf.Get<float>(),p.M);
            oq.EnQue(yy);yy=oq.DeQue<float>();AscendC::DataCopyExtParams oc{1,4,0,0,0};
            AscendC::DataCopyPad(out[batch],yy,oc);oq.FreeTensor(yy);bmms71::Fence<AscendC::HardEvent::V_MTE2>(*pipe_);
        }
    }
};

}

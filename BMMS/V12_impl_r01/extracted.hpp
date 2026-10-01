// BMMS1201_BEGIN
namespace bmms1201 {
using Plan=bmms11r2::Plan;
using bmms83::MinI;
constexpr int TM=bmms11r2::TM,TN=bmms11r2::TN,AM=bmms11r2::AM,BN=bmms11r2::BN;
constexpr int MACRO_ELEMS=bmms11r2::MACRO_ELEMS;
constexpr uint16_t READY=bmms11r2::READY,FREE=bmms11r2::FREE;
static inline bool Eligible(int B,int M,int N,int K,int cores){
    return B==1&&M>=1024&&N>=1024&&K>=1536&&K<2048&&cores>=2&&
        bmms11r2::Eligible(B,M,N,K,cores);
}
// Work units come from the unchanged AM128/BN256 producer, not measured cycles.
struct Work {uint64_t macro,mmad,cells,input;};
static inline Work Peak(const Plan& p){
    if(p.tasks==p.blocks){
        const auto g=bmms11r2::SingleWavePeak(p);
        const uint64_t mr=bmms11r2::PeakExtent(p.M,AM,p.pM),nr=bmms11r2::PeakExtent(p.N,BN,p.pN);
        return Work{g.tiles,((mr+TM-1)/TM)*((nr+TN-1)/TN),g.cells,g.input};
    }
    Work peak{};
    for(int group=0;group<p.blocks;++group){
        Work w{};
        for(int task=group;task<p.tasks;task+=p.blocks){
            const int ms=(task%(p.pM*p.pN))/p.pN,ns=task%p.pN;
            const int mt0=ms*p.mTiles/p.pM,mt1=(ms+1)*p.mTiles/p.pM;
            const int nt0=ns*p.nTiles/p.pN,nt1=(ns+1)*p.nTiles/p.pN;
            const uint64_t mr=bmms83::MinH(mt1*AM,p.M)-mt0*AM,nr=bmms83::MinH(nt1*BN,p.N)-nt0*BN;
            w.macro+=uint64_t(mt1-mt0)*(nt1-nt0);w.mmad+=((mr+TM-1)/TM)*((nr+TN-1)/TN);
            w.cells+=mr*nr;w.input+=mr*(nt1-nt0)+nr*(mt1-mt0);
        }
        if(w.macro>peak.macro)peak.macro=w.macro;if(w.mmad>peak.mmad)peak.mmad=w.mmad;
        if(w.cells>peak.cells)peak.cells=w.cells;if(w.input>peak.input)peak.input=w.input;
    }
    return peak;
}
static inline bool NoWorse(const Work& x,const Work& base){
    return x.macro<=base.macro&&x.mmad<=base.mmad&&x.cells<=base.cells&&x.input<=base.input;
}
static inline bool Better(const Work& x,int pn,const Work& best,int bestPn){
    if(x.mmad!=best.mmad)return x.mmad<best.mmad;
    if(x.macro!=best.macro)return x.macro<best.macro;
    if(x.cells!=best.cells)return x.cells<best.cells;
    if(x.input!=best.input)return x.input<best.input;
    return pn<bestPn;
}
static inline Plan MakePlan(int B,int M,int N,int K,int cores){
    const Plan base=bmms11r2::MakePlan(B,M,N,K,cores);
    if(!Eligible(B,M,N,K,cores))return base;
    const Work bound=Peak(base);Work bestWork=bound;Plan best=base;
    const int minGroups=(3*cores+3)/4;
    for(int pm=1;pm<=bmms83::MinH(base.mTiles,cores);++pm){
        const int lo=bmms83::MaxH(1,bmms83::UpH(minGroups,pm));
        const int hi=bmms83::MinH(base.pN,bmms83::MinH(base.nTiles,cores/pm));
        for(int pn=lo;pn<=hi;++pn){
            Plan candidate=base;candidate.pM=pm;candidate.pN=pn;
            candidate.tasks=pm*pn;candidate.blocks=candidate.tasks;
            const Work w=Peak(candidate);
            if(NoWorse(w,bound)&&Better(w,pn,bestWork,best.pN)){best=candidate;bestWork=w;}
        }
    }
    return best;
}

// Original macro ring and row ownership. Only read/reduce live columns.
class CompactConsumer {
    Plan p;AscendC::TPipe* pipe_;
    AscendC::GlobalTensor<float> ring,part,out;
    AscendC::TQue<AscendC::TPosition::VECIN,1> cq0,cq1;
    AscendC::TQue<AscendC::TPosition::VECOUT,1> oq;
    AscendC::TBuf<AscendC::TPosition::VECCALC> rowBuf,sumBuf;
    AscendC::TBuf<AscendC::TPosition::VECOUT> runningBuf;
    AscendC::TBuf<AscendC::TPosition::VECIN> mergedBuf,tmpBuf;
public:
    __aicore__ inline void Init(GM_ADDR r,GM_ADDR pt,GM_ADDR y,const Plan& plan,AscendC::TPipe* pipe){
        p=plan;pipe_=pipe;
        ring.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(r),int64_t(p.blocks)*2*MACRO_ELEMS);
        part.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(pt),int64_t(p.B)*p.pN*p.M);
        out.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(y),p.B);
        pipe->InitBuffer(cq0,1,(TM/2)*TN*4);pipe->InitBuffer(cq1,1,(TM/2)*TN*4);pipe->InitBuffer(oq,1,32);
        pipe->InitBuffer(rowBuf,(TM/2)*4);pipe->InitBuffer(runningBuf,AM*4);
        pipe->InitBuffer(mergedBuf,p.M*4);pipe->InitBuffer(tmpBuf,p.M*4);pipe->InitBuffer(sumBuf,p.M*4);
    }
    __aicore__ inline void Process(){
        const int worker=AscendC::GetBlockIdx(),group=worker/2,sub=worker%2,perBatch=p.pM*p.pN;
        int seq=0;auto rows=rowBuf.Get<float>(),run=runningBuf.Get<float>();
        for(int task=group;task<p.tasks;task+=p.blocks){
            const int batch=task/perBatch,slot=task-batch*perBatch,ms=slot/p.pN,ns=slot%p.pN;
            const int mt0=ms*p.mTiles/p.pM,mt1=(ms+1)*p.mTiles/p.pM;
            const int nt0=ns*p.nTiles/p.pN,nt1=(ns+1)*p.nTiles/p.pN;
            const int mBegin=mt0*AM,mEnd=MinI(mt1*AM,p.M),nBegin=nt0*BN,nEnd=MinI(nt1*BN,p.N);
            for(int mBase=mBegin;mBase<mEnd;mBase+=AM){
                const int ar=MinI(AM,mEnd-mBase);
                for(int nBase=nBegin;nBase<nEnd;nBase+=BN){
                    const int br=MinI(BN,nEnd-nBase),ringSlot=seq&1;
                    AscendC::CrossCoreWaitFlag<0x2>(READY+ringSlot);
                    for(int mo=0;mo<ar;mo+=TM){
                        const int mr=MinI(TM,ar-mo),vr=mr/2;
                        const int nr=MinI(TN,br),ci=(mo/TM)*2;
                        const int64_t off=(int64_t(group)*2+ringSlot)*MACRO_ELEMS+ci*TM*TN+sub*vr*TN;
                        auto c=cq0.AllocTensor<float>();
                        AscendC::DataCopyExtParams cp{static_cast<uint16_t>(vr),uint32_t(nr*4),uint32_t((TN-nr)*4),0,0};
                        AscendC::DataCopyPadExtParams<float> pd{false,0,0,0.0f};
                        AscendC::DataCopyPad(c,ring[off],cp,pd);cq0.EnQue(c);c=cq0.DeQue<float>();
                        if(br>TN){
                            const int nr1=br-TN;auto d=cq1.AllocTensor<float>();
                            AscendC::DataCopyExtParams cp1{static_cast<uint16_t>(vr),uint32_t(nr1*4),uint32_t((TN-nr1)*4),0,0};
                            AscendC::DataCopyPad(d,ring[off+TM*TN],cp1,pd);cq1.EnQue(d);d=cq1.DeQue<float>();
                            if(mo+mr==ar)AscendC::CrossCoreSetFlag<0x2,PIPE_MTE2>(FREE+ringSlot);
                            if(nr1==TN){AscendC::Max(c,c,d,vr*TN);}
                            else{
                                const AscendC::BinaryRepeatParams rp{1,1,1,16,16,static_cast<uint8_t>(nr1/8)};
                                for(int n=0;n<nr1;n+=64)AscendC::Max(c[n],c[n],d[n],MinI(64,nr1-n),vr,rp);
                            }
                            AscendC::PipeBarrier<PIPE_V>();cq1.FreeTensor(d);
                        }else if(mo+mr==ar){AscendC::CrossCoreSetFlag<0x2,PIPE_MTE2>(FREE+ringSlot);}
                        if(nr>64){
                            const uint8_t stride=static_cast<uint8_t>(nr/8);
                            const AscendC::BinaryRepeatParams rp{1,1,1,stride,stride,stride};
                            AscendC::Max(c,c,c[64],nr-64,vr,rp);AscendC::PipeBarrier<PIPE_V>();
                        }
                        const bool first=nBase==nBegin;auto dst=first?run[mo+sub*vr]:rows;
                        AscendC::WholeReduceMax(dst,c,MinI(nr,64),vr,1,1,nr/8,AscendC::ReduceOrder::ORDER_ONLY_VALUE);
                        AscendC::PipeBarrier<PIPE_V>();
                        if(!first){AscendC::Max(run[mo+sub*vr],run[mo+sub*vr],rows,vr);AscendC::PipeBarrier<PIPE_V>();}
                        cq0.FreeTensor(c);
                    }
                    ++seq;
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

} // namespace bmms1201

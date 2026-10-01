// BMMS48_BEGIN
namespace bmms48 {
using Plan=bmms83::NativePlan;
constexpr int32_t TM=64,TN=128;
constexpr uint16_t READY=4,FREE=6;
static inline bool Eligible(int B,int M,int N,int K,int cores){
    return B>1&&B<cores&&M<128&&N<256&&K<512&&bmms11d::ResidualEligible(B,M,N,K,cores);
}
static inline Plan MakePlan(int B,int M,int N,int K,int cores){
    Plan p=bmms11d::MakePlan(B,M,N,K,cores);
    p.pM=1;p.pN=1;p.tasks=B;p.blocks=bmms83::MinH(cores,B);return p;
}
static inline uint64_t RingBytes(const Plan& p){return bmms11d::RingBytes(p);}
static inline uint64_t WorkspaceBytes(const Plan& p){return RingBytes(p);}
// A Cube group owns complete batches. One AIV reads every row; both return credits.
// K128 staged producer and full-M summation order are retained without a global barrier.
class BatchConsumer {
    Plan p;AscendC::TPipe* pipe_;
    AscendC::GlobalTensor<float> ring,out;
    AscendC::TQue<AscendC::TPosition::VECIN,1> cq;
    AscendC::TQue<AscendC::TPosition::VECOUT,1> oq;
    AscendC::TBuf<AscendC::TPosition::VECCALC> accBuf,runBuf,sumBuf;
public:
    __aicore__ inline void Init(GM_ADDR r,GM_ADDR pt,GM_ADDR y,const Plan& plan,AscendC::TPipe* pipe){
        p=plan;pipe_=pipe;
        ring.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(r),int64_t(p.blocks)*2*TM*TN);
        out.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(y),p.B);
        pipe->InitBuffer(cq,1,TM*TN*4);pipe->InitBuffer(oq,1,32);
        pipe->InitBuffer(accBuf,TM*TN*4);
        pipe->InitBuffer(runBuf,p.M*4);pipe->InitBuffer(sumBuf,p.M*4);
    }
    __aicore__ inline void Process(){
        const int worker=AscendC::GetBlockIdx(),group=worker/2,sub=worker%2;
        int seq=0;auto acc=accBuf.Get<float>();auto run=runBuf.Get<float>();
        for(int batch=group;batch<p.B;batch+=p.blocks){
            const bool owner=sub==(batch&1);
            // Guard guarantees M<AM and N<BN, so this is the producer's exact tile order.
            for(int m=0;m<p.M;m+=TM){
                const int mr=bmms83::MinI(TM,p.M-m);
                if(owner){AscendC::Duplicate(acc,bmmmaxsum_v43::NEG_INF,mr*TN);AscendC::PipeBarrier<PIPE_V>();}
                for(int n=0;n<p.N;n+=TN){
                    const int nr=bmms83::MinI(TN,p.N-n),slot=seq&1;
                    AscendC::CrossCoreWaitFlag<0x2>(READY+slot);
                    if(owner){
                        auto c=cq.AllocTensor<float>();
                        AscendC::Duplicate(c,bmmmaxsum_v43::NEG_INF,mr*TN);
                        bmms71::Fence<AscendC::HardEvent::V_MTE2>(*pipe_);
                        AscendC::DataCopyExtParams cp{static_cast<uint16_t>(mr),uint32_t(nr*4),uint32_t((TN-nr)*4),uint32_t((TN-nr)/8),0};
                        AscendC::DataCopyPadExtParams<float> pd{false,0,0,0.0f};
                        AscendC::DataCopyPad(c,ring[(int64_t(group)*2+slot)*TM*TN],cp,pd);
                        cq.EnQue(c);c=cq.DeQue<float>();
                        AscendC::Max(acc,acc,c,mr*TN);AscendC::PipeBarrier<PIPE_V>();cq.FreeTensor(c);
                    }
                    AscendC::CrossCoreSetFlag<0x2,PIPE_MTE2>(FREE+slot);++seq;
                }
                if(owner){
                    AscendC::BinaryRepeatParams rp{1,1,1,16,16,16};
                    AscendC::Max(acc,acc,acc[64],64,mr,rp);AscendC::PipeBarrier<PIPE_V>();
                    AscendC::WholeReduceMax(run[m],acc,64,mr,1,1,16,AscendC::ReduceOrder::ORDER_ONLY_VALUE);
                    AscendC::PipeBarrier<PIPE_V>();
                }
            }
            if(owner){
                auto yy=oq.AllocTensor<float>();AscendC::ReduceSum(yy,run,sumBuf.Get<float>(),p.M);
                oq.EnQue(yy);yy=oq.DeQue<float>();AscendC::DataCopyExtParams oc{1,4,0,0,0};
                AscendC::DataCopyPad(out[batch],yy,oc);oq.FreeTensor(yy);
            }
        }
    }
};
template<class T,bool TA,bool TB>
__aicore__ inline void Entry(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ring,GM_ADDR partial,Plan p){
    AscendC::TPipe pipe;
    if ASCEND_IS_AIC {bmms11d::StagedProducer<T,TA,TB> op;op.Init(a,b,ring,p,&pipe);op.Process();}
    if ASCEND_IS_AIV {BatchConsumer op;op.Init(ring,partial,y,p,&pipe);op.Process();}
}
} // namespace bmms48

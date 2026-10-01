// BMMS49_BEGIN
namespace bmms49 {
using Plan=bmms83::NativePlan;
using bmms83::MinI;
constexpr int32_t TM=bmms83::TM,TN=bmms83::TN,AM=bmms83::AM,PACKET_TILES=bmms83::PACKET_TILES;
constexpr uint16_t READY=bmms83::READY,FREE=bmms83::FREE;
static inline bool Select(const Plan& p){
    return p.B==1&&p.K==128&&p.M>256&&p.M<=8192&&p.M%16==0&&
        (p.N==48||p.N==64)&&p.pN==1&&p.blocks>1;
}
// Original producer, M partition, 4-tile packet and partial layout are retained.
// With one complete N<=64 panel, load valid columns compactly and reduce directly.
class NarrowPacketConsumer {
    Plan p;AscendC::TPipe* pipe_;
    AscendC::GlobalTensor<float> ring,part,out;
    AscendC::TQue<AscendC::TPosition::VECIN,1> cq;
    AscendC::TQue<AscendC::TPosition::VECOUT,1> oq;
    AscendC::TBuf<AscendC::TPosition::VECOUT> runningBuf;
    AscendC::TBuf<AscendC::TPosition::VECIN> mergedBuf;
    AscendC::TBuf<AscendC::TPosition::VECCALC> sumBuf;
public:
    __aicore__ inline void Init(GM_ADDR r,GM_ADDR pt,GM_ADDR y,const Plan& plan,AscendC::TPipe* pipe){
        p=plan;pipe_=pipe;
        ring.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(r),int64_t(p.blocks)*2*PACKET_TILES*TM*TN);
        part.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(pt),p.M);
        out.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(y),1);
        pipe->InitBuffer(cq,1,(TM/2)*64*4);pipe->InitBuffer(oq,1,32);
        pipe->InitBuffer(runningBuf,AM*4);pipe->InitBuffer(mergedBuf,p.M*4);pipe->InitBuffer(sumBuf,p.M*4);
    }
    __aicore__ inline void Process(){
        const int worker=AscendC::GetBlockIdx(),group=worker/2,sub=worker%2;
        int seq=0;auto run=runningBuf.Get<float>();
        for(int task=group;task<p.tasks;task+=p.blocks){
            // Select guarantees B=1,pN=1; task is exactly the original M shard.
            const int mBegin=(task*p.mTiles/p.pM)*TM,mEnd=MinI(((task+1)*p.mTiles/p.pM)*TM,p.M);
            for(int mBase=mBegin;mBase<mEnd;mBase+=AM){
                const int ar=MinI(AM,mEnd-mBase);
                for(int mo=0;mo<ar;mo+=TM){
                    const int mr=MinI(TM,ar-mo),vr=mr/2;
                    const int packetSlot=(seq/PACKET_TILES)&1,tileSlot=seq%PACKET_TILES;
                    if(tileSlot==0)AscendC::CrossCoreWaitFlag<0x2>(READY+packetSlot);
                    auto c=cq.AllocTensor<float>();
                    const int64_t off=((int64_t(group)*2+packetSlot)*PACKET_TILES+tileSlot)*TM*TN+sub*vr*TN;
                    AscendC::DataCopyExtParams cp{static_cast<uint16_t>(vr),uint32_t(p.N*4),uint32_t((TN-p.N)*4),0,0};
                    AscendC::DataCopyPadExtParams<float> pd{false,0,0,0.0f};
                    AscendC::DataCopyPad(c,ring[off],cp,pd);cq.EnQue(c);c=cq.DeQue<float>();
                    if(tileSlot+1==PACKET_TILES)AscendC::CrossCoreSetFlag<0x2,PIPE_MTE2>(FREE+packetSlot);
                    // Every row is complete; neither padded columns nor earlier
                    // run contents participate in the row maximum.
                    AscendC::WholeReduceMax(run[mo+sub*vr],c,p.N,vr,1,1,p.N/8,AscendC::ReduceOrder::ORDER_ONLY_VALUE);
                    AscendC::PipeBarrier<PIPE_V>();cq.FreeTensor(c);++seq;
                }
                bmms71::Fence<AscendC::HardEvent::V_MTE3>(*pipe_);
                for(int mo=0;mo<ar;mo+=TM){
                    const int vr=MinI(TM,ar-mo)/2;
                    AscendC::DataCopyExtParams rp{1,uint32_t(vr*4),0,0,0};
                    AscendC::DataCopyPad(part[mBase+mo+sub*vr],run[mo+sub*vr],rp);
                }
                bmms71::Fence<AscendC::HardEvent::MTE3_V>(*pipe_);
            }
        }
        if(seq%PACKET_TILES)AscendC::CrossCoreSetFlag<0x2,PIPE_MTE2>(FREE+((seq/PACKET_TILES)&1));
        bmms71::Fence<AscendC::HardEvent::MTE3_MTE2>(*pipe_);AscendC::SyncAll<true>();
        if(worker==0){
            auto merged=mergedBuf.Get<float>();
            AscendC::DataCopyExtParams mp{1,uint32_t(p.M*4),0,0,0};
            AscendC::DataCopyPadExtParams<float> pd{false,0,0,0.0f};
            AscendC::DataCopyPad(merged,part,mp,pd);
            bmms71::Fence<AscendC::HardEvent::MTE2_V>(*pipe_);
            auto yy=oq.AllocTensor<float>();AscendC::ReduceSum(yy,merged,sumBuf.Get<float>(),p.M);
            oq.EnQue(yy);yy=oq.DeQue<float>();AscendC::DataCopyExtParams oc{1,4,0,0,0};
            AscendC::DataCopyPad(out,yy,oc);oq.FreeTensor(yy);
        }
    }
};

template<class T,bool TA,bool TB>
__aicore__ inline void Entry(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ring,GM_ADDR partial,Plan p){
    AscendC::TPipe pipe;
    if ASCEND_IS_AIC {bmms83::SmallKProducer<T,TA,TB,128> op;op.Init(a,b,ring,p,&pipe);op.Process();}
    if ASCEND_IS_AIV {NarrowPacketConsumer op;op.Init(ring,partial,y,p,&pipe);op.Process();}
}
} // namespace bmms49

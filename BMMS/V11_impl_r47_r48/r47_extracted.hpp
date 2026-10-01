// BMMS47_BEGIN
namespace bmms47 {
using Plan=bmms83::NativePlan;
using NativePlan=Plan;
using bmms83::MinI;
constexpr int32_t TM=64,TN=64,AM=256,BN=64,PACKET_TILES=1;
constexpr uint16_t READY=4,FREE=6;
static inline bool Eligible(int B,int M,int N,int K,int cores){
    return B==1&&K==128&&M>256&&M<=8192&&M%16==0&&(N==48||N==64)&&cores>=2&&cores<=64;
}
static inline Plan MakePlan(int B,int M,int N,int K,int cores){
    // mTiles denotes 16-row scheduling units in this namespace, not Cube tiles.
    Plan p{};p.B=B;p.M=M;p.N=N;p.K=K;p.mTiles=M/16;p.nTiles=1;
    p.pM=bmms83::MinH(cores,p.mTiles);p.pN=1;p.tasks=p.pM;p.blocks=p.tasks;return p;
}
static inline uint64_t RingBytes(const Plan& p){return uint64_t(p.blocks)*2*TM*TN*4;}
static inline uint64_t WorkspaceBytes(const Plan& p){return RingBytes(p)+uint64_t(p.M)*4;}
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
            const int mBegin=mt0*16,mEnd=MinI(mt1*16,p.M);
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

// N is one complete 48/64-column panel. No padded columns enter the maximum.
// Preserve one row maximum per M, then the baseline's single full-M ReduceSum.
class NarrowConsumer {
    Plan p;AscendC::TPipe* pipe_;
    AscendC::GlobalTensor<float> ring,part,out;
    AscendC::TQue<AscendC::TPosition::VECIN,1> cq;
    AscendC::TQue<AscendC::TPosition::VECOUT,1> oq;
    AscendC::TBuf<AscendC::TPosition::VECOUT> rowBuf;
    AscendC::TBuf<AscendC::TPosition::VECIN> mergedBuf;
    AscendC::TBuf<AscendC::TPosition::VECCALC> sumBuf;
public:
    __aicore__ inline void Init(GM_ADDR r,GM_ADDR pt,GM_ADDR y,const Plan& plan,AscendC::TPipe* pipe){
        p=plan;pipe_=pipe;
        ring.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(r),int64_t(p.blocks)*2*TM*TN);
        part.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(pt),p.M);
        out.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(y),1);
        pipe->InitBuffer(cq,1,(TM/2)*TN*4);pipe->InitBuffer(oq,1,32);
        pipe->InitBuffer(rowBuf,(TM/2)*4);pipe->InitBuffer(mergedBuf,p.M*4);pipe->InitBuffer(sumBuf,p.M*4);
    }
    __aicore__ inline void Process(){
        const int worker=AscendC::GetBlockIdx(),group=worker/2,sub=worker%2;
        const int mBegin=(group*p.mTiles/p.pM)*16,mEnd=MinI(((group+1)*p.mTiles/p.pM)*16,p.M);
        int seq=0;
        for(int m=mBegin;m<mEnd;m+=TM){
            const int mr=MinI(TM,mEnd-m),vr=mr/2,slot=seq&1;
            AscendC::CrossCoreWaitFlag<0x2>(READY+slot);
            auto c=cq.AllocTensor<float>();
            const int64_t off=(int64_t(group)*2+slot)*TM*TN+sub*vr*TN;
            AscendC::DataCopyExtParams cp{static_cast<uint16_t>(vr),uint32_t(p.N*4),uint32_t((TN-p.N)*4),0,0};
            AscendC::DataCopyPadExtParams<float> pd{false,0,0,0.0f};
            AscendC::DataCopyPad(c,ring[off],cp,pd);cq.EnQue(c);c=cq.DeQue<float>();
            AscendC::CrossCoreSetFlag<0x2,PIPE_MTE2>(FREE+slot);
            auto rows=rowBuf.Get<float>();
            AscendC::WholeReduceMax(rows,c,p.N,vr,1,1,p.N/8,AscendC::ReduceOrder::ORDER_ONLY_VALUE);
            bmms71::Fence<AscendC::HardEvent::V_MTE3>(*pipe_);
            AscendC::DataCopyExtParams rp{1,uint32_t(vr*4),0,0,0};
            AscendC::DataCopyPad(part[m+sub*vr],rows,rp);
            bmms71::Fence<AscendC::HardEvent::MTE3_V>(*pipe_);
            cq.FreeTensor(c);++seq;
        }
        bmms71::Fence<AscendC::HardEvent::MTE3_MTE2>(*pipe_);
        AscendC::SyncAll<true>();
        if(worker==0){
            auto merged=mergedBuf.Get<float>();AscendC::DataCopy(merged,part,p.M);
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
    if ASCEND_IS_AIC {SmallKProducer<T,TA,TB,128> op;op.Init(a,b,ring,p,&pipe);op.Process();}
    if ASCEND_IS_AIV {NarrowConsumer op;op.Init(ring,partial,y,p,&pipe);op.Process();}
}
} // namespace bmms47

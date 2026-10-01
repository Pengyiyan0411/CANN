// BMMS1203_BEGIN
namespace bmms1203 {
using Plan=bmms50::Plan;
static inline bool Eligible(int B,int M,int N,int K){return bmms50::Eligible(B,M,N,K);}
static inline Plan MakePlan(int M,int N,int K){return bmms50::MakePlan(M,N,K);}
template<class T,bool TA,bool TB,int K>
__aicore__ inline void Device(GM_ADDR a,GM_ADDR b,GM_ADDR y,const Plan& p){
    AscendC::TPipe pipe;
    constexpr int kp=K<=32?32:K<=64?64:128;
    constexpr bool DIRECT_A=!TA&&K==kp,DIRECT_B=TB&&K==kp;
    const int M=p.M,N=p.N,D=M*N,nr=(N+7)/8*8;
    const int ar=(M*K+15)/16*16,br=(N*K+15)/16*16;
    const int af=(M*K+7)/8*8,bf=(N*K+7)/8*8;
    const int dotSize=p.tiny?D*8:M*nr;
    const int scratchSize=p.tiny?D*kp:(kp>M*8?kp:M*8);
    AscendC::TQue<AscendC::TPosition::VECIN,1> iq;
    AscendC::TQue<AscendC::TPosition::VECOUT,1> oq;
    AscendC::TBuf<AscendC::TPosition::VECCALC> floats,indices,packed,products,values,scratch;
    pipe.InitBuffer(iq,1,(ar+br)*sizeof(T));pipe.InitBuffer(oq,1,32);
    pipe.InitBuffer(floats,(af+bf)*4);pipe.InitBuffer(indices,2*kp*4);
    pipe.InitBuffer(packed,((DIRECT_A?0:M)+(DIRECT_B?0:N))*kp*4+32);pipe.InitBuffer(products,D*kp*4);
    pipe.InitBuffer(values,(dotSize+M*8)*4);pipe.InitBuffer(scratch,scratchSize*4);
    auto fa=floats.Get<float>(),fb=fa[af];
    auto pack=packed.Get<float>();
    auto bp=DIRECT_B?fb:pack,ap=DIRECT_A?fa:pack[(DIRECT_B?0:N)*kp],prod=products.Get<float>();
    auto dots=values.Get<float>(),rows=dots[dotSize],tmp=scratch.Get<float>();
    auto ia=indices.Get<int32_t>(),ib=ia[kp];
    if constexpr(!DIRECT_A)AscendC::CreateVecIndex(ia,int32_t(0),K);
    if constexpr(!DIRECT_B)AscendC::CreateVecIndex(ib,int32_t(0),K);
    AscendC::PipeBarrier<PIPE_V>();
    if constexpr(!DIRECT_A)AscendC::Muls(ia,ia,int32_t((TA?M:1)*4),K);
    if constexpr(!DIRECT_B)AscendC::Muls(ib,ib,int32_t((TB?1:N)*4),K);
    AscendC::PipeBarrier<PIPE_V>();
    auto iau=ia.template ReinterpretCast<uint32_t>(),ibu=ib.template ReinterpretCast<uint32_t>();
    AscendC::GlobalTensor<T> ga,gb;AscendC::GlobalTensor<float> gy;
    ga.SetGlobalBuffer(reinterpret_cast<__gm__ T*>(a),M*K);gb.SetGlobalBuffer(reinterpret_cast<__gm__ T*>(b),N*K);
    gy.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(y),1);
    auto in=iq.AllocTensor<T>();AscendC::DataCopyPadExtParams<T> pd{false,0,0,T(0)};
    AscendC::DataCopyExtParams ac{1,uint32_t(M*K*sizeof(T)),0,0,0},bc{1,uint32_t(N*K*sizeof(T)),0,0,0};
    AscendC::DataCopyPad(in,ga,ac,pd);AscendC::DataCopyPad(in[ar],gb,bc,pd);
    iq.EnQue(in);in=iq.DeQue<T>();
    AscendC::Cast(fa,in,AscendC::RoundMode::CAST_NONE,M*K);AscendC::Cast(fb,in[ar],AscendC::RoundMode::CAST_NONE,N*K);
    if constexpr(!DIRECT_B)AscendC::Duplicate(bp,0.0f,N*kp);
    if constexpr(!DIRECT_A)AscendC::Duplicate(ap,0.0f,M*kp);
    AscendC::Duplicate(rows,0.0f,M*8);
    if(p.tiny)AscendC::Duplicate(dots,bmmmaxsum_v43::NEG_INF,dotSize);
    AscendC::PipeBarrier<PIPE_V>();
    if constexpr(!DIRECT_B)for(int n=0;n<N;++n)AscendC::Gather(bp[n*kp],fb,ibu,uint32_t((TB?n*K:n)*4),K);
    if constexpr(!DIRECT_A)for(int m=0;m<M;++m)AscendC::Gather(ap[m*kp],fa,iau,uint32_t((TA?m:m*K)*4),K);
    AscendC::PipeBarrier<PIPE_V>();
    const uint8_t stride=static_cast<uint8_t>(kp/8);
    const AscendC::BinaryRepeatParams mulp{1,1,1,stride,0,stride};
    for(int m=0;m<M;++m)for(int k=0;k<kp;k+=64)
        AscendC::Mul(prod[m*N*kp+k],ap[m*kp+k],bp[k],bmms83::MinI(kp,64),N,mulp);
    AscendC::PipeBarrier<PIPE_V>();
    if(p.tiny){
        // Separate scratch per dot permits independent reductions without
        // an inter-dot barrier. Padding never participates in ReduceSum(K).
        for(int d=0;d<D;++d)AscendC::ReduceSum(dots[d*8],prod[d*kp],tmp[d*kp],K);
        AscendC::PipeBarrier<PIPE_V>();
        AscendC::WholeReduceMax(rows,dots,N*8,M,8,1,N,AscendC::ReduceOrder::ORDER_ONLY_VALUE);
    }else{
        if(kp==128){
            const AscendC::BinaryRepeatParams addp{1,1,1,16,16,16};
            for(int d=0;d<D;d+=255)
                AscendC::Add(prod[d*kp],prod[d*kp],prod[d*kp+64],64,bmms83::MinI(255,D-d),addp);
            AscendC::PipeBarrier<PIPE_V>();
        }
        for(int m=0;m<M;++m)
            AscendC::WholeReduceSum(dots[m*nr],prod[m*N*kp],bmms83::MinI(kp,64),N,1,1,kp/8);
        AscendC::PipeBarrier<PIPE_V>();
        AscendC::WholeReduceMax(rows,dots,N,M,8,1,nr/8,AscendC::ReduceOrder::ORDER_ONLY_VALUE);
    }
    AscendC::PipeBarrier<PIPE_V>();
    auto out=oq.AllocTensor<float>();AscendC::ReduceSum(out,rows,tmp,M*8);
    oq.EnQue(out);out=oq.DeQue<float>();AscendC::DataCopyExtParams cp{1,4,0,0,0};
    AscendC::DataCopyPad(gy,out,cp);oq.FreeTensor(out);iq.FreeTensor(in);
}
} // namespace bmms1203

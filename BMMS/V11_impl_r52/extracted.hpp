// BMMS52_BEGIN
namespace bmms52 {
static inline bool Eligible(int B,int M,int N,int K){
    return B==1&&M==1&&N==1&&K>=32&&K<=128&&K%8==0;
}
// Exact Dot arithmetic; constant K removes batch iteration and dynamic layout setup.
template<class T,int K>
__aicore__ inline void Device(GM_ADDR a,GM_ADDR b,GM_ADDR y){
    static_assert(K>=32&&K<=128&&K%8==0,"short dot domain");
    constexpr int KP=(K+15)/16*16;
    AscendC::TPipe pipe;
    AscendC::TQue<AscendC::TPosition::VECIN,1> iq;
    AscendC::TQue<AscendC::TPosition::VECOUT,1> oq;
    AscendC::TBuf<AscendC::TPosition::VECCALC> floats,scratch;
    pipe.InitBuffer(iq,1,2*KP*sizeof(T));pipe.InitBuffer(oq,1,32);
    pipe.InitBuffer(floats,2*KP*4);pipe.InitBuffer(scratch,KP*4);
    AscendC::GlobalTensor<T> ga,gb;AscendC::GlobalTensor<float> gy;
    ga.SetGlobalBuffer(reinterpret_cast<__gm__ T*>(a),K);
    gb.SetGlobalBuffer(reinterpret_cast<__gm__ T*>(b),K);
    gy.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(y),1);
    auto in=iq.AllocTensor<T>();
    AscendC::DataCopyExtParams cp{1,uint32_t(K*sizeof(T)),0,0,0};
    AscendC::DataCopyPadExtParams<T> pad{false,0,0,T(0)};
    AscendC::DataCopyPad(in,ga,cp,pad);AscendC::DataCopyPad(in[KP],gb,cp,pad);
    iq.EnQue(in);in=iq.DeQue<T>();auto fa=floats.Get<float>(),fb=fa[KP];
    if constexpr(K==KP){
        AscendC::Cast(fa,in,AscendC::RoundMode::CAST_NONE,2*K);
    }else{
        AscendC::Cast(fa,in,AscendC::RoundMode::CAST_NONE,K);
        AscendC::Cast(fb,in[KP],AscendC::RoundMode::CAST_NONE,K);
    }
    AscendC::PipeBarrier<PIPE_V>();AscendC::Mul(fa,fa,fb,K);
    AscendC::PipeBarrier<PIPE_V>();auto out=oq.AllocTensor<float>();
    AscendC::ReduceSum(out,fa,scratch.Get<float>(),K);
    oq.EnQue(out);out=oq.DeQue<float>();AscendC::DataCopyExtParams oc{1,4,0,0,0};
    AscendC::DataCopyPad(gy,out,oc);oq.FreeTensor(out);iq.FreeTensor(in);
}
} // namespace bmms52

namespace bmmmaxsum_v43 {
constexpr float NEG_INF=-__builtin_inff();
inline int MinI(int a,int b){return a<b?a:b;}
static inline bool UseTiny(int32_t M, int32_t N, int32_t K)
{
    return int64_t(M)*N<=16 && K<=1024 && int64_t(M)*N*K<=8192;
}
template <typename T, bool TA, bool TB>
__aicore__ inline void TinyDevice(GM_ADDR a, GM_ADDR b, GM_ADDR y,
    int32_t B, int32_t M, int32_t N, int32_t K, int32_t workers)
{
    AscendC::TPipe pipe;
    const int32_t ar = (M * K + 15) / 16 * 16;
    const int32_t br = (N * K + 15) / 16 * 16;
    const int32_t af = (M * K + 7) / 8 * 8;
    const int32_t bf = (N * K + 7) / 8 * 8;
    const int32_t kp = (K + 7) / 8 * 8;
    const int32_t dotPad = (N + 7) / 8 * 64;
    AscendC::TQue<AscendC::TPosition::VECIN, 1> iq;
    AscendC::TQue<AscendC::TPosition::VECOUT, 1> oq;
    AscendC::TBuf<AscendC::TPosition::VECCALC> fbuf, idxbuf, packbuf, scratch, vals;
    pipe.InitBuffer(iq, 1, (ar + br) * sizeof(T));
    pipe.InitBuffer(oq, 1, 32);
    pipe.InitBuffer(fbuf, (af + bf) * sizeof(float));
    pipe.InitBuffer(idxbuf, 2 * kp * sizeof(int32_t));
    pipe.InitBuffer(packbuf, (N + 2) * kp * sizeof(float));
    pipe.InitBuffer(scratch, (kp > 8 * M ? kp : 8 * M) * sizeof(float));
    pipe.InitBuffer(vals, (dotPad + 8 * M) * sizeof(float));
    auto ia = idxbuf.Get<int32_t>();
    auto ib = ia[kp];
    AscendC::CreateVecIndex(ia, int32_t(0), K);
    AscendC::CreateVecIndex(ib, int32_t(0), K);
    AscendC::PipeBarrier<PIPE_V>();
    AscendC::Muls(ia, ia, int32_t((TA ? M : 1) * sizeof(float)), K);
    AscendC::Muls(ib, ib, int32_t((TB ? 1 : N) * sizeof(float)), K);
    AscendC::PipeBarrier<PIPE_V>();
    auto iau = ia.template ReinterpretCast<uint32_t>();
    auto ibu = ib.template ReinterpretCast<uint32_t>();
    auto fa = fbuf.Get<float>();
    auto fb = fa[af];
    auto bp = packbuf.Get<float>();
    auto av = bp[N * kp];
    auto prod = av[kp];
    auto tmp = scratch.Get<float>();
    auto dots = vals.Get<float>();
    auto rows = dots[dotPad];
    AscendC::GlobalTensor<T> ga, gb;
    AscendC::GlobalTensor<float> gy;
    ga.SetGlobalBuffer(reinterpret_cast<__gm__ T*>(a), int64_t(B) * M * K);
    gb.SetGlobalBuffer(reinterpret_cast<__gm__ T*>(b), int64_t(B) * N * K);
    gy.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(y), B);
    const int32_t id = static_cast<int32_t>(AscendC::GetBlockIdx());
    for (int32_t batch = id; batch < B; batch += workers) {
        auto in = iq.AllocTensor<T>();
        AscendC::DataCopyPadExtParams<T> pad{false, 0, 0, 0};
        AscendC::DataCopyExtParams acp{1, uint32_t(M * K * sizeof(T)), 0, 0, 0};
        AscendC::DataCopyExtParams bcp{1, uint32_t(N * K * sizeof(T)), 0, 0, 0};
        AscendC::DataCopyPad(in, ga[int64_t(batch) * M * K], acp, pad);
        AscendC::DataCopyPad(in[ar], gb[int64_t(batch) * N * K], bcp, pad);
        iq.EnQue(in);
        in = iq.DeQue<T>();
        AscendC::Cast(fa, in, AscendC::RoundMode::CAST_NONE, M * K);
        AscendC::Cast(fb, in[ar], AscendC::RoundMode::CAST_NONE, N * K);
        AscendC::Duplicate(rows, 0.0f, 8 * M);
        AscendC::PipeBarrier<PIPE_V>();
        for (int32_t n = 0; n < N; ++n) {
            AscendC::Gather(bp[n * kp], fb, ibu,
                uint32_t((TB ? n * K : n) * sizeof(float)), K);
        }
        AscendC::PipeBarrier<PIPE_V>();
        for (int32_t m = 0; m < M; ++m) {
            AscendC::Gather(av, fa, iau,
                uint32_t((TA ? m : m * K) * sizeof(float)), K);
            AscendC::Duplicate(dots, NEG_INF, dotPad);
            AscendC::PipeBarrier<PIPE_V>();
            for (int32_t n = 0; n < N; ++n) {
                AscendC::Mul(prod, av, bp[n * kp], K);
                AscendC::PipeBarrier<PIPE_V>();
                AscendC::ReduceSum(dots[n * 8], prod, tmp, K);
                AscendC::PipeBarrier<PIPE_V>();
            }
            if (N > 8) {
                AscendC::Max(dots, dots, dots[64], 64);
                AscendC::PipeBarrier<PIPE_V>();
            }
            AscendC::WholeReduceMax(rows[m * 8], dots, MinI(64, N * 8),
                1, 1, 1, 8, AscendC::ReduceOrder::ORDER_ONLY_VALUE);
            AscendC::PipeBarrier<PIPE_V>();
        }
        auto out = oq.AllocTensor<float>();
        AscendC::ReduceSum(out, rows, tmp, M * 8);
        oq.EnQue(out);
        out = oq.DeQue<float>();
        AscendC::DataCopyExtParams cp{1, sizeof(float), 0, 0, 0};
        AscendC::DataCopyPad(gy[batch], out, cp);
        oq.FreeTensor(out);
        iq.FreeTensor(in);
    }
}
}
namespace bmms71 {
inline int MinI(int a,int b){return a<b?a:b;}
static inline int32_t Pow2Up(int32_t x,int32_t limit){int32_t r=16;while(r<x&&r<limit)r*=2;return r;}
static inline bool UseResident(int32_t M,int32_t N,int32_t K){
    return M<=32&&N<=64&&K<=128&&int64_t(M)*N<=256&&int64_t(M)*N*K<=16384&&int64_t(M+N)*K<=8192;
}
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
}
namespace bmms83 {inline int MinI(int a,int b){return a<b?a:b;}}

"""Independent R50 child: static short dot with exact original FP32 reduction."""
from pathlib import Path
import importlib.util,hashlib,json
H=Path(__file__).resolve().parent;ROOT=H.parent;OUT=ROOT/'BMMS_V11_R52'
BASE=ROOT/'BMMS_V11_R50/R50_SINGLE_BATCH_SMALL_VECTOR.asc'
SHA='97484e6d79152d131ec9f45697611379e98c894aa9a94707638601024c2935ec';NAME='R52_SHORT_DOT_STATIC'
sp=importlib.util.spec_from_file_location('r52_helpers',ROOT/'V11_impl_r50/build.py');r50=importlib.util.module_from_spec(sp);sp.loader.exec_module(r50)
write,once,between,function,host=r50.write,r50.once,r50.between,r50.function,r50.host
def module():
    s='''// BMMS52_BEGIN
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
// BMMS52_CPU_END
#define BMMS52_KERNEL(NAME,T,K) \\
__global__ __aicore__ void NAME(GM_ADDR a,GM_ADDR b,GM_ADDR y){bmms52::Device<T,K>(a,b,y);}
'''
    for dt,t in [('f16','half'),('b16','bfloat16_t')]:
        for k in range(32,129,8):s+=f'BMMS52_KERNEL(bmms52_{dt}_k{k},{t},{k})\n'
    s+='''#undef BMMS52_KERNEL
namespace bmms52 {
static inline bool TryLaunch(GM_ADDR a,GM_ADDR b,GM_ADDR y,int B,int M,int N,int K,
    int dtype,aclrtStream stream){
    if((dtype!=1&&dtype!=2)||!Eligible(B,M,N,K))return false;
#define BMMS52_LAUNCH(NAME) NAME<<<1,nullptr,stream>>>(a,b,y)
'''
    for i,dt in enumerate(['f16','b16']):
        s+=('    if(dtype==1){\n' if i==0 else '    }else{\n')+'        switch(K){\n'
        for k in range(32,129,8):s+=f'        case {k}: BMMS52_LAUNCH(bmms52_{dt}_k{k});return true;\n'
        s+='        }\n'
    return s+'''    }
#undef BMMS52_LAUNCH
    return false;
}
} // namespace bmms52
// BMMS52_END

'''
def main():
    raw=BASE.read_bytes();assert hashlib.sha256(raw).hexdigest()==SHA;OUT.mkdir(exist_ok=True)
    fragment=module().encode();anchor=b'extern "C" void run_kernel(GM_ADDR a,const TensorGroupInfo& ia,'
    assert raw.count(anchor)==1;data=raw.replace(anchor,fragment+anchor,1)
    marker=b'    if(bmms11r2::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;'
    hook=b'    if(bmms52::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,stream))return;\r\n'
    assert data.count(marker)==1;data=data.replace(marker,hook+marker,1)
    assert data.replace(fragment,b'',1).replace(hook,b'',1)==raw
    (OUT/(NAME+'.asc')).write_bytes(data);write(H/'extracted.hpp',between(module(),'// BMMS52_BEGIN','// BMMS52_CPU_END'))
    m={'candidate':NAME+'.asc','sha256':hashlib.sha256(data).hexdigest(),'parent_R50_sha256':SHA,
       'parent_recovered_byte_for_byte':True,'scope':'B=M=N=1, K32..128 step8, both input dtypes',
       'kernel_variants':26,'kernel_launches_per_call':1,'AIV_workers':1,'GM_workspace_bytes':0,
       'arithmetic':'same FP32 Cast/Mul/ReduceSum(K) as original Dot; fused Cast only if K%16==0',
       'preserved':['R50 Case2','R49 Case13','R48 Case7','R25 Case5','R43 Case8','R23 Case15'],
       'includes_R51':False}
    write(OUT/'MANIFEST.json',json.dumps(m,indent=2)+'\n');print(json.dumps(m,indent=2))
if __name__=='__main__':main()

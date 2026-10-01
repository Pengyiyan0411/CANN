"""Extend measured R50 row staging to independent batches; leave R50 intact."""
from pathlib import Path
import importlib.util,hashlib,json
H=Path(__file__).resolve().parent;ROOT=H.parent;OUT=ROOT/'BMMS_V11_R51'
BASE=ROOT/'BMMS_V11_R50/R50_SINGLE_BATCH_SMALL_VECTOR.asc'
SHA='97484e6d79152d131ec9f45697611379e98c894aa9a94707638601024c2935ec'
NAME='R51_BATCHED_SMALL_VECTOR'
sp=importlib.util.spec_from_file_location('r51_helpers',ROOT/'V11_impl_r50/build.py');r50=importlib.util.module_from_spec(sp);sp.loader.exec_module(r50)
write,once,between,function,host=r50.write,r50.once,r50.between,r50.function,r50.host

def module():
    dev=(ROOT/'V11_impl_r50/device.inc').read_text(encoding='utf-8')
    dev=once(dev,'// Batch the independent row work on one AIV. No row partials or Cube rendezvous.',
        '// R50 row staging, with one independent batch owner and persistent UB per AIV.')
    dev=once(dev,'reinterpret_cast<__gm__ T*>(a),M*K','reinterpret_cast<__gm__ T*>(a),int64_t(p.B)*M*K')
    dev=once(dev,'reinterpret_cast<__gm__ T*>(b),N*K','reinterpret_cast<__gm__ T*>(b),int64_t(p.B)*N*K')
    dev=once(dev,'reinterpret_cast<__gm__ float*>(y),1);','reinterpret_cast<__gm__ float*>(y),p.B);\n    for(int batch=AscendC::GetBlockIdx();batch<p.B;batch+=p.workers){')
    dev=once(dev,'DataCopyPad(in,ga,ac,pd)','DataCopyPad(in,ga[int64_t(batch)*M*K],ac,pd)')
    dev=once(dev,'DataCopyPad(in[ar],gb,bc,pd)','DataCopyPad(in[ar],gb[int64_t(batch)*N*K],bc,pd)')
    dev=once(dev,'DataCopyPad(gy,out,cp)','DataCopyPad(gy[batch],out,cp)')
    dev=once(dev,'oq.FreeTensor(out);iq.FreeTensor(in);','oq.FreeTensor(out);iq.FreeTensor(in);\n    }')
    s='''// BMMS51_BEGIN
namespace bmms51 {
struct Plan {int32_t B,M,N,K,kp,tiny,workers;};
static inline bool Eligible(int B,int M,int N,int K){
    return B>1&&B<=64&&bmms50::Eligible(1,M,N,K);
}
static inline Plan MakePlan(int B,int M,int N,int K,int cores){
    const auto q=bmms50::MakePlan(M,N,K);
    return Plan{B,M,N,K,q.kp,q.tiny,B<2*cores?B:2*cores};
}
'''+dev+'''\n} // namespace bmms51
// BMMS51_CPU_END
#define BMMS51_KERNEL(NAME,T,TA,TB) \\
__global__ __aicore__ void NAME(GM_ADDR a,GM_ADDR b,GM_ADDR y,bmms51::Plan p){bmms51::Device<T,TA,TB>(a,b,y,p);}
'''
    for dt,t in [('f16','half'),('b16','bfloat16_t')]:
        for suffix,ta,tb in [('nn','false','false'),('nt','false','true'),('tn','true','false'),('tt','true','true')]:
            s+=f'BMMS51_KERNEL(bmms51_{dt}_{suffix},{t},{ta},{tb})\n'
    s+='''#undef BMMS51_KERNEL
namespace bmms51 {
static inline bool TryLaunch(GM_ADDR a,GM_ADDR b,GM_ADDR y,int B,int M,int N,int K,
    int dtype,bool ta,bool tb,int cores,aclrtStream stream){
    if((dtype!=1&&dtype!=2)||!Eligible(B,M,N,K))return false;
    const Plan p=MakePlan(B,M,N,K,cores);
#define BMMS51_LAUNCH(NAME) NAME<<<p.workers,nullptr,stream>>>(a,b,y,p)
'''
    for i,dt in enumerate(['f16','b16']):
        s+=('    if(dtype==1){\n' if i==0 else '    }else{\n')
        for j,(suf,cond) in enumerate([('nn','!ta&&!tb'),('nt','!ta&&tb'),('tn','ta&&!tb'),('tt','')]):
            s+=('        if' if j==0 else '        else if' if j<3 else '        else')+(f'({cond})' if cond else '')+f'{{BMMS51_LAUNCH(bmms51_{dt}_{suf});}}\n'
    return s+'''    }
#undef BMMS51_LAUNCH
    return true;
}
} // namespace bmms51
// BMMS51_END

'''

def main():
    raw=BASE.read_bytes();assert hashlib.sha256(raw).hexdigest()==SHA;OUT.mkdir(exist_ok=True)
    fragment=module().encode();anchor=b'extern "C" void run_kernel(GM_ADDR a,const TensorGroupInfo& ia,'
    assert raw.count(anchor)==1;data=raw.replace(anchor,fragment+anchor,1)
    marker=b'    if(bmms11r2::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;'
    hook=b'    if(bmms51::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\r\n'
    assert data.count(marker)==1;data=data.replace(marker,hook+marker,1)
    assert data.replace(fragment,b'',1).replace(hook,b'',1)==raw
    (OUT/(NAME+'.asc')).write_bytes(data)
    write(H/'extracted.hpp',between(module(),'// BMMS51_BEGIN','// BMMS51_CPU_END'))
    manifest={'candidate':NAME+'.asc','sha256':hashlib.sha256(data).hexdigest(),'parent_R50_sha256':SHA,
       'parent_recovered_byte_for_byte':True,'scope':'B2..64 M/N2..16 K32..128 K%8=0 AND original Tiny/Resident',
       'workers':'min(B,2*normalized_availableCoreNum), identical to original Tiny/Resident',
       'kernel_launches':1,'GM_workspace_bytes':0,'explicit_host_sync':False,'cross_core_barrier':False,
       'preserved':['R50 Case2','R49 Case13','R48 Case7','R25 Case5','R43 Case8','R23 Case15']}
    write(OUT/'MANIFEST.json',json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()

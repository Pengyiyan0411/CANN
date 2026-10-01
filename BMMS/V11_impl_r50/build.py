from pathlib import Path
import hashlib,json,importlib.util
H=Path(__file__).resolve().parent;ROOT=H.parent;OUT=ROOT/'BMMS_V11_R50'
BASE=ROOT/'BMMS_V11_R49/R49_NATIVE_CONSUMER_ONLY.asc'
SHA='8a84f77ecba35da1bff9eec7856ef12f4ea7ea3b85e40166695e82a0302272fc'
NAME='R50_SINGLE_BATCH_SMALL_VECTOR'
sp=importlib.util.spec_from_file_location('r50_helpers',ROOT/'V11_impl_r47_r48/build.py');old=importlib.util.module_from_spec(sp);sp.loader.exec_module(old)
write,once,between,function,host=old.write,old.once,old.between,old.function,old.host
def module():
    s='''// BMMS50_BEGIN
namespace bmms50 {
struct Plan {int32_t M,N,K,kp,tiny;};
static inline bool Eligible(int B,int M,int N,int K){
    return B==1&&M>=2&&M<=16&&N>=2&&N<=16&&K>=32&&K<=128&&K%8==0&&
        (bmmmaxsum_v43::UseTiny(M,N,K)||bmms71::UseResident(M,N,K));
}
static inline Plan MakePlan(int M,int N,int K){
    return Plan{M,N,K,bmms71::Pow2Up(K,128),int(bmmmaxsum_v43::UseTiny(M,N,K))};
}
'''+(H/'device.inc').read_text(encoding='utf-8')+'''
} // namespace bmms50
// BMMS50_CPU_END
#define BMMS50_KERNEL(NAME,T,TA,TB) \\
__global__ __aicore__ void NAME(GM_ADDR a,GM_ADDR b,GM_ADDR y,bmms50::Plan p){bmms50::Device<T,TA,TB>(a,b,y,p);}
'''
    for dt,t in [('f16','half'),('b16','bfloat16_t')]:
        for suffix,ta,tb in [('nn','false','false'),('nt','false','true'),('tn','true','false'),('tt','true','true')]:
            s+=f'BMMS50_KERNEL(bmms50_{dt}_{suffix},{t},{ta},{tb})\n'
    s+='''#undef BMMS50_KERNEL
namespace bmms50 {
static inline bool TryLaunch(GM_ADDR a,GM_ADDR b,GM_ADDR y,int B,int M,int N,int K,
    int dtype,bool ta,bool tb,aclrtStream stream){
    if((dtype!=1&&dtype!=2)||!Eligible(B,M,N,K))return false;
    const Plan p=MakePlan(M,N,K);
#define BMMS50_LAUNCH(NAME) NAME<<<1,nullptr,stream>>>(a,b,y,p)
'''
    for i,dt in enumerate(['f16','b16']):
        s+=('    if(dtype==1){\n' if i==0 else '    }else{\n')
        for j,(suf,cond) in enumerate([('nn','!ta&&!tb'),('nt','!ta&&tb'),('tn','ta&&!tb'),('tt','')]):
            s+=('        if' if j==0 else '        else if' if j<3 else '        else')+(f'({cond})' if cond else '')+f'{{BMMS50_LAUNCH(bmms50_{dt}_{suf});}}\n'
    return s+'''    }
#undef BMMS50_LAUNCH
    return true; // vector-only, no workspace or explicit host synchronization
}
} // namespace bmms50
// BMMS50_END

'''
def main():
    raw=BASE.read_bytes();assert hashlib.sha256(raw).hexdigest()==SHA;OUT.mkdir(exist_ok=True)
    fragment=module().encode();anchor=b'extern "C" void run_kernel(GM_ADDR a,const TensorGroupInfo& ia,'
    assert raw.count(anchor)==1;data=raw.replace(anchor,fragment+anchor,1)
    marker=b'    if(bmms11r2::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;'
    hook=b'    if(bmms50::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,stream))return;\r\n'
    assert data.count(marker)==1;data=data.replace(marker,hook+marker,1)
    assert data.replace(fragment,b'',1).replace(hook,b'',1)==raw
    (OUT/(NAME+'.asc')).write_bytes(data)
    write(H/'extracted.hpp',between(module(),'// BMMS50_BEGIN','// BMMS50_CPU_END'))
    m={'candidate':NAME+'.asc','sha256':hashlib.sha256(data).hexdigest(),'parent_R49_sha256':SHA,
       'parent_recovered_byte_for_byte':True,'kernel_launches':1,'AIV_workers':1,'GM_workspace_bytes':0,
       'scope':'B1 M/N2..16 K32..128 K%8=0 AND existing Tiny/Resident route',
       'preserved':['R49 Case13','R48 Case7','R25 Case5','R43 Case8','R23 Case15']}
    write(OUT/'MANIFEST.json',json.dumps(m,indent=2)+'\n');print(json.dumps(m,indent=2))
if __name__=='__main__':main()

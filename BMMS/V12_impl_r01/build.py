from pathlib import Path
import importlib.util,hashlib,json,shutil
H=Path(__file__).resolve().parent;ROOT=H.parent;OUT=ROOT/'BMMS_V12'
BASE=ROOT/'BMMS_V11_R52/R52_SHORT_DOT_STATIC.asc';SHA='3c66689f4a38b4b6b02aa92547b39065a55d3fdfbcf767d6a53a4618f34cc284'
NAME='V12_01_CASE12_DENSE'
sp=importlib.util.spec_from_file_location('v12_helpers',ROOT/'V11_impl_r49/build.py');old=importlib.util.module_from_spec(sp);sp.loader.exec_module(old)
write,once,between,function,host=old.write,old.once,old.between,old.function,old.host
def module():
    s='''// BMMS1201_BEGIN
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
'''+(H/'planner.inc').read_text(encoding='utf-8')+'\n'+(H/'consumer.inc').read_text(encoding='utf-8')
    s+='''
} // namespace bmms1201
// BMMS1201_CPU_END
namespace bmms1201 {
template<class T,bool TA,bool TB>
__aicore__ inline void Entry(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ring,GM_ADDR part,Plan p){
    AscendC::TPipe pipe;
    if ASCEND_IS_AIC {bmms11r2::ReuseProducer<T,TA,TB> op;op.Init(a,b,ring,p,&pipe);op.Process();}
    if ASCEND_IS_AIV {CompactConsumer op;op.Init(ring,part,y,p,&pipe);op.Process();}
}
}
#define BMMS1201_KERNEL(NAME,T,TA,TB) \\
__schedmode__(1) __global__ __mix__(1,2) void NAME(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ring,GM_ADDR part,bmms1201::Plan p){bmms1201::Entry<T,TA,TB>(a,b,y,ring,part,p);}
'''
    for dt,T in [('f16','half'),('b16','bfloat16_t')]:
        for suf,ta,tb in [('nn','false','false'),('nt','false','true'),('tn','true','false'),('tt','true','true')]:
            s+=f'BMMS1201_KERNEL(bmms1201_{dt}_{suf},{T},{ta},{tb})\n'
    s+='#undef BMMS1201_KERNEL\nnamespace bmms1201 {\n'
    h=host(BASE.read_text(encoding='utf-8'),'bmms11r2')
    h=h.replace('BMMS11R2_LAUNCH','BMMS1201_LAUNCH').replace('bmms11r2_f16','bmms1201_f16').replace('bmms11r2_b16','bmms1201_b16')
    h=h.replace('WorkspaceBytes(p)','bmms11r2::WorkspaceBytes(p)').replace('ws+RingBytes(p)','ws+bmms11r2::RingBytes(p)')
    return s+h+'\n} // namespace bmms1201\n// BMMS1201_END\n\n'
def main():
    raw=BASE.read_bytes();assert hashlib.sha256(raw).hexdigest()==SHA;OUT.mkdir(exist_ok=True)
    frozen=OUT/'V12_BASELINE_R52.asc'
    if frozen.exists():assert frozen.read_bytes()==raw
    else:shutil.copyfile(BASE,frozen)
    fragment=module().encode();anchor=b'extern "C" void run_kernel(GM_ADDR a,const TensorGroupInfo& ia,'
    assert raw.count(anchor)==1;data=raw.replace(anchor,fragment+anchor,1)
    mark=b'    if(bmms11r2::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;'
    hook=b'    if(bmms1201::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\r\n'
    assert data.count(mark)==1;data=data.replace(mark,hook+mark,1)
    assert data.replace(fragment,b'',1).replace(hook,b'',1)==raw
    (OUT/(NAME+'.asc')).write_bytes(data);write(H/'extracted.hpp',between(module(),'// BMMS1201_BEGIN','// BMMS1201_CPU_END'))
    m={'candidate':NAME+'.asc','sha256':hashlib.sha256(data).hexdigest(),'parent_R52_sha256':SHA,
      'R52_recovered_byte_for_byte':True,'scope':'B1 M/N>=1024 and16aligned K1536..2016 step32 original R06 eligible cores>=2',
      'new_producer':False,'original_R06_K1_K0':[256,64],'original_R06_AM_BN':[128,256],
      'new_consumer':'compact live-column max, unchanged macro ownership and final M sum',
      'planner':'single wave Pareto bounds versus original peak work, pN never increased; otherwise original plan',
      'includes_R51':False,'contains_diagnostic_stress':False}
    write(OUT/'MANIFEST.json',json.dumps(m,indent=2)+'\n')
    state={'line':'V12','accepted_sota':'V12_BASELINE_R52.asc','accepted_sha256':SHA,
      'acceptance_basis':'user explicitly named R52 current SOTA; quantitative R52 table not supplied',
      'candidate':NAME+'.asc','candidate_status':'awaiting CANN/Judge validation','legacy_frozen':'V11_analysis_r43/R43_CASE8_PADDED_MACRO.asc'}
    write(OUT/'MAINLINE.json',json.dumps(state,indent=2)+'\n');print(json.dumps(m,indent=2))
if __name__=='__main__':main()

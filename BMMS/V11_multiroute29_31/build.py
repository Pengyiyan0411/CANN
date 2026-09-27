"""Three isolated producer experiments; every file starts at the frozen R25."""
from pathlib import Path
import hashlib,json,shutil,difflib
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;OUT=ROOT/'BMMS_V11_R29_R30_R31'
BASE=ROOT/'BMMS_V11_R25/R25_NATIVE_TARGETED.asc'
BASE_SHA='7defd06457ddb0e356cbf4cc8407f31cbb7c622acf6efd66070be212fa4eacb2'
NAMES={29:'R29_SHORTK_L1',30:'R30_NATIVE_M128',31:'R31_MACRO_K128'}
ANCHOR='extern "C" void run_kernel(GM_ADDR a,const TensorGroupInfo& ia,'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,s):p.write_text(s,encoding='utf-8',newline='\n')
def once(s,a,b):assert s.count(a)==1,(s.count(a),a[:120]);return s.replace(a,b,1)
def between(s,a,b):i=s.index(a);return s[i:s.index(b,i)]
def function(s,mark):
    i=s.index(mark);j=s.index('{',i)+1;depth=1
    while depth:depth+=(s[j]=='{')-(s[j]=='}');j+=1
    return s[i:j]
def host(old,ns):return function(old[old.index('namespace '+ns+' {\nstatic inline bool TryLaunch('):],'static inline bool TryLaunch(')

def binding(n,producer,consumer):
    ns=f'bmms{n}'
    s=f'''template<class T,bool TA,bool TB>
__aicore__ inline void Entry(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ring,GM_ADDR partial,Plan p){{
    AscendC::TPipe pipe;
    if ASCEND_IS_AIC {{{producer} op;op.Init(a,b,ring,p,&pipe);op.Process();}}
    if ASCEND_IS_AIV {{{consumer} op;op.Init(ring,partial,y,p,&pipe);op.Process();}}
}}
}} // namespace {ns}
// BMMS{n}_CPU_EXTRACT_END
#define BMMS{n}_KERNEL(NAME,T,TA,TB) \\
__schedmode__(1) __global__ __mix__(1,2) void NAME(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ring,GM_ADDR part,{ns}::Plan p){{{ns}::Entry<T,TA,TB>(a,b,y,ring,part,p);}}
'''
    for dt,T in [('f16','half'),('b16','bfloat16_t')]:
        for layout,ta,tb in [('nn','false','false'),('nt','false','true'),('tn','true','false'),('tt','true','true')]:
            s+=f'BMMS{n}_KERNEL({ns}_{dt}_{layout},{T},{ta},{tb})\n'
    return s+f'#undef BMMS{n}_KERNEL\nnamespace {ns} {{\n'

def r29(base):
    old=between(base,'namespace bmms11d {','// BMMS9_CPU_EXTRACT_END')
    prod=between(old,'template<class T,bool TA,bool TB>\nclass StagedProducer','\n#ifndef BMMS9_CPU_TEST')
    prod=once(prod,'class StagedProducer','class ResidentKProducer')
    prod=once(prod,'__aicore__ inline void LoadL0(int mr,int nr,int kr,int stage)',
                   '__aicore__ inline void LoadL0(int mr,int nr,int k0,int kr,int stage)')
    prod=once(prod,'auto srcA=a1Buf.template Get<T>()[stage*TM*KB];','auto srcA=a1Buf.template Get<T>();')
    prod=once(prod,'auto srcB=b1Buf.template Get<T>()[stage*KB*TN];','auto srcB=b1Buf.template Get<T>();')
    prod=once(prod,'const int off=TA?i*kr*16:i*256;','const int off=TA?i*p.K*16+k0*16:(k0/16)*mr*16+i*256;')
    prod=once(prod,'lb.srcStride=TB?1:kr/16;','lb.srcStride=TB?1:p.K/16;')
    prod=once(prod,'const int off=TB?j*nr*16:j*256;','const int off=TB?(k0/16+j)*nr*16:(k0/16+j)*256;')
    prod=once(prod,'        // Input L1 slot may be overwritten only after both LoadData streams.\n        AscendC::SetFlag<AscendC::HardEvent::MTE1_MTE2>(l1Free[stage]);\n','')
    prod=once(prod,'LoadStage(batch,m0,n0,mr,nr,0,bmms83::MinI(KB,p.K),0);',
        'LoadStage(batch,m0,n0,mr,nr,0,p.K,0);\n        AscendC::WaitFlag<AscendC::HardEvent::MTE2_MTE1>(l1Ready[0]);')
    start='            AscendC::WaitFlag<AscendC::HardEvent::MTE2_MTE1>(l1Ready[stage]);'
    end='            if(ki>=2)AscendC::WaitFlag<AscendC::HardEvent::M_MTE1>(l0Free[stage]);'
    prod=once(prod,between(prod,start,end),'')
    prod=once(prod,'LoadL0(mr,nr,kr,stage);','LoadL0(mr,nr,k0,kr,stage);')
    prod=once(prod,'            AscendC::WaitFlag<AscendC::HardEvent::MTE1_MTE2>(l1Free[stage]);\n','')
    mark='        AscendC::SetFlag<AscendC::HardEvent::M_FIX>(cReady);'
    prod=once(prod,mark,'        // Full-K L1 stays immutable until every L0 slice has been read.\n        AscendC::SetFlag<AscendC::HardEvent::MTE1_MTE2>(l1Free[0]);\n        AscendC::WaitFlag<AscendC::HardEvent::MTE1_MTE2>(l1Free[0]);\n'+mark)
    prod=once(prod,'pipe->InitBuffer(a1Buf,2*TM*KB*sizeof(T));pipe->InitBuffer(b1Buf,2*KB*TN*sizeof(T));',
        'pipe->InitBuffer(a1Buf,TM*MAX_K*sizeof(T));pipe->InitBuffer(b1Buf,MAX_K*TN*sizeof(T));')
    prod=once(prod,between(prod,'    // Compact ND2NZ tiles','    __aicore__ inline void LoadStage'),
        '    // One compact full-K L1 stage per output tile. L0 still uses K128 chunks.\n')
    prefix='''// BMMS29_BEGIN: short residual K, full-K L1 and unchanged K128 accumulation.
namespace bmms29 {
using Plan=bmms11d::Plan;
constexpr int32_t TM=64,TN=128,AM=256,BN=512,KB=128,MAX_K=512;
constexpr uint16_t READY=bmms83::READY,FREE=bmms83::FREE;
static inline bool Eligible(int B,int M,int N,int K,int cores){
    return bmms11d::ResidualEligible(B,M,N,K,cores)&&M<128&&N<256&&K<512&&B<cores;
}
'''
    h=host(base,'bmms11d').replace('ResidualEligible(','Eligible(')
    h=h.replace('const auto p=MakePlan(','const auto p=bmms11d::MakePlan(').replace('WorkspaceBytes(p)','bmms11d::WorkspaceBytes(p)').replace('RingBytes(p)','bmms11d::RingBytes(p)')
    h=h.replace('BMMS11D_LAUNCH','BMMS29_LAUNCH').replace('bmms11d_f16','bmms29_f16').replace('bmms11d_b16','bmms29_b16')
    return prefix+prod+binding(29,'ResidentKProducer<T,TA,TB>','bmms83::SmallKConsumer')+h+'\n}\n// BMMS29_END\n\n'

def r30(base):
    old=between(base,'namespace bmms83 {\nconstexpr int32_t TM=64','class SmallKConsumer {')
    prefix=old[:old.index('template<class T,bool TA,bool TB,int TK>\nclass SmallKProducer')]
    prefix=once(prefix,'namespace bmms83 {','// BMMS30_BEGIN: M128 Native producer and matching row-half consumer.\nnamespace bmms30 {')
    prefix=once(prefix,'TM=64, TN=128','TM=128, TN=128')
    prefix=once(prefix,between(prefix,'struct NativePlan {','static inline bool NativeEligible'),
        'using NativePlan=bmms83::NativePlan;\nusing Plan=NativePlan;\n\n')
    prefix=once(prefix,'PACKET_TILES=4;','PACKET_TILES=2;')
    prefix+='''static inline bool Select(const NativePlan& p){
    return p.K==128&&p.B==1&&p.M>=128&&p.N>32&&p.blocks>1;
}
'''
    prod=between(old,'template<class T,bool TA,bool TB,int TK>\nclass SmallKProducer','class SmallKConsumer {') if 'class SmallKConsumer {' in old else old[old.index('template<class T,bool TA,bool TB,int TK>\nclass SmallKProducer'):]
    # The original producer ends immediately before SmallKConsumer.
    consumer=between(base,'class DenseGatherConsumer {','template<class T,bool TA,bool TB,bool SMALL>')
    consumer=once(consumer,'(16384/p.pN/16)*16','(8192/p.pN/16)*16')
    h='''static inline bool TryLaunch(GM_ADDR a,GM_ADDR b,GM_ADDR y,const NativePlan& old,int dtype,bool ta,bool tb,int cores,aclrtStream stream){
    if(!Select(old))return false;
    const auto p=MakeNative(old.B,old.M,old.N,old.K,cores);
    uint8_t* ws=nullptr;const uint64_t rb=bmms30::NativeRingBytes(p),pb=bmms30::NativePartialBytes(p);
    if(aclrtMalloc(reinterpret_cast<void**>(&ws),rb+pb,ACL_MEM_MALLOC_HUGE_FIRST)!=ACL_SUCCESS)std::abort();
    uint8_t* partial=ws+rb;
#define BMMS30_LAUNCH(NAME) NAME<<<p.blocks,nullptr,stream>>>(a,b,y,ws,partial,p)
'''
    for dt,T in [(1,'f16'),(2,'b16')]:
        h+=('    if(dtype==1){\n' if dt==1 else '    }else{\n')
        for idx,(layout,cond) in enumerate([('nn','!ta&&!tb'),('nt','!ta&&tb'),('tn','ta&&!tb'),('tt','ta&&tb')]):
            h+=('        if' if idx==0 else '        else if')+f'({cond}){{BMMS30_LAUNCH(bmms30_{T}_{layout});}}\n'
    h+='''    }
#undef BMMS30_LAUNCH
    if(aclrtSynchronizeStream(stream)!=ACL_SUCCESS)std::abort();
    if(aclrtFree(ws)!=ACL_SUCCESS)std::abort();return true;
}
'''
    return prefix+prod+consumer+binding(30,'SmallKProducer<T,TA,TB,128>','DenseGatherConsumer')+h+'}\n// BMMS30_END\n\n'

def r31(base):
    old=between(base,'namespace bmms11r2 {','// BMMS11R2_CPU_EXTRACT_END')
    prod=between(old,'template<class T,bool TA,bool TB>\nclass ReuseProducer','class RowMaxConsumer {')
    prod=once(prod,'const int s0=l0Count&1,kr0=MinI(K0,kr1-kk);','const int s0=0,kr0=MinI(K0,kr1-kk);')
    prod=once(prod,'if(l0Count>=2)','if(l0Count>=1)')
    prod=once(prod,'s<MinI(2,l0Count)','s<MinI(1,l0Count)')
    prod=once(prod,'pipe->InitBuffer(a2Buf,2*AM*K0*sizeof(T));pipe->InitBuffer(b2Buf,2*K0*BN*sizeof(T));',
        'pipe->InitBuffer(a2Buf,AM*K0*sizeof(T));pipe->InitBuffer(b2Buf,K0*BN*sizeof(T));')
    prefix='''// BMMS31_BEGIN: Macro K128 single L0, original double L1 and output macro protocol.
namespace bmms31 {
using Plan=bmms11r2::Plan;
using bmms83::MinI;
constexpr int32_t TM=64,TN=128,AM=128,BN=256,K1=256,K0=128,MACRO_ELEMS=4*TM*TN;
constexpr uint16_t READY=bmms83::READY,FREE=bmms83::FREE;
static inline bool Eligible(int B,int M,int N,int K,int cores){return bmms11r2::Eligible(B,M,N,K,cores);}
'''
    h=host(base,'bmms11r2')
    h=h.replace('const auto p=MakePlan(','const auto p=bmms11r2::MakePlan(').replace('WorkspaceBytes(p)','bmms11r2::WorkspaceBytes(p)').replace('RingBytes(p)','bmms11r2::RingBytes(p)')
    h=h.replace('BMMS11R2_LAUNCH','BMMS31_LAUNCH').replace('bmms11r2_f16','bmms31_f16').replace('bmms11r2_b16','bmms31_b16')
    return prefix+prod+binding(31,'ReuseProducer<T,TA,TB>','bmms11r2::RowMaxConsumer')+h+'\n}\n// BMMS31_END\n\n'

def call(n):
    if n==30:return '        if(bmms30::TryLaunch(a,b,y,p,x.dtype,ta,tb,cores,stream))return;\n'
    return f'    if(bmms{n}::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
def anchor(n):
    if n==30:return '        if(bmms25::TryLaunch(a,b,y,p,x.dtype,ta,tb,stream))return;'
    ns='bmms11d' if n==29 else 'bmms11r2'
    return f'    if({ns}::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;'
def fragment(n,base):return {29:r29,30:r30,31:r31}[n](base)
def verify():
    assert sha(BASE)==sha(OUT/'CONTROL_R25.asc')==BASE_SHA
    base=BASE.read_text(encoding='utf-8');r={}
    for n,name in NAMES.items():
        s=(OUT/(name+'.asc')).read_text(encoding='utf-8')
        restored=once(once(s,fragment(n,base),''),call(n),'')
        assert restored.split('\n',1)[1]==base.split('\n',1)[1]
        r[name]={'all_original_functions_byte_identical':True,'one_guarded_hook':True,'baseline':BASE_SHA}
    return r
def main():
    assert sha(BASE)==BASE_SHA;OUT.mkdir(exist_ok=True)
    base=BASE.read_text(encoding='utf-8');shutil.copyfile(BASE,OUT/'CONTROL_R25.asc')
    for n,name in NAMES.items():
        f=fragment(n,base);write(HERE/(name+'_fragment.asc'),f)
        s=once(base,ANCHOR,f+ANCHOR);s=once(s,anchor(n),call(n)+anchor(n))
        s=once(s,s.split('\n',1)[0],f'// {name}: isolated producer experiment on frozen R25; platform validation pending.')
        write(OUT/(name+'.asc'),s)
        write(HERE/(name+'.diff'),''.join(difflib.unified_diff(base.splitlines(True),s.splitlines(True),fromfile='R25',tofile=name)))
    m={'base_sha256':BASE_SHA,'files':{p.name:sha(p) for p in OUT.glob('*.asc')},'composition':verify(),
       'CANN_compiled_locally':False,'NPU_tested_locally':False,'platform_results_pending':True}
    write(OUT/'MANIFEST.json',json.dumps(m,indent=2)+'\n');print(json.dumps(m['composition']))
if __name__=='__main__':main()

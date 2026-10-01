"""Two independent, byte-reversible additions to the frozen R43."""
from pathlib import Path
import hashlib, json, importlib.util
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
OUT=ROOT/'BMMS_V11_R47_R48'
BASE=ROOT/'V11_analysis_r43/R43_CASE8_PADDED_MACRO.asc'
SHA='15e2c9a0f73e7534c26400107389dcd8e5cf685b5f6f477c7a3684ad3991df2d'
NAMES={47:'R47_NATIVE_NARROW_DIRECT',48:'R48_RESIDUAL_BATCH_OWNER'}
def write(p,s): p.write_text(s,encoding='utf-8',newline='\n')
def once(s,a,b):
    assert s.count(a)==1,(s.count(a),a[:100])
    return s.replace(a,b,1)
def between(s,a,z):
    i=s.index(a);return s[i:s.index(z,i)]
def function(s,mark):
    i=s.index(mark);j=s.index('{',i)+1;d=1
    while d:d+=(s[j]=='{')-(s[j]=='}');j+=1
    return s[i:j]
def host(s,ns):
    return function(s[s.index('namespace '+ns+' {\nstatic inline bool TryLaunch('):],'static inline bool TryLaunch(')
def bindings(n,producer,consumer):
    ns=f'bmms{n}'
    s=f'''template<class T,bool TA,bool TB>
__aicore__ inline void Entry(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ring,GM_ADDR partial,Plan p){{
    AscendC::TPipe pipe;
    if ASCEND_IS_AIC {{{producer} op;op.Init(a,b,ring,p,&pipe);op.Process();}}
    if ASCEND_IS_AIV {{{consumer} op;op.Init(ring,partial,y,p,&pipe);op.Process();}}
}}
}} // namespace {ns}
// BMMS{n}_CPU_END
#define BMMS{n}_KERNEL(NAME,T,TA,TB) \\
__schedmode__(1) __global__ __mix__(1,2) void NAME(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ring,GM_ADDR part,{ns}::Plan p){{{ns}::Entry<T,TA,TB>(a,b,y,ring,part,p);}}
'''
    for dt,T in [('f16','half'),('b16','bfloat16_t')]:
        for layout,ta,tb in [('nn','false','false'),('nt','false','true'),('tn','true','false'),('tt','true','true')]:
            s+=f'BMMS{n}_KERNEL({ns}_{dt}_{layout},{T},{ta},{tb})\n'
    return s+f'#undef BMMS{n}_KERNEL\nnamespace {ns} {{\n'
def module(n,base):
    if n==47:
        prefix='''// BMMS47_BEGIN
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
'''
        producer=between(base,'template<class T,bool TA,bool TB,int TK>\nclass SmallKProducer','class SmallKConsumer {')
        producer=once(producer,'const int mBegin=mt0*TM,mEnd=MinI(mt1*TM,p.M);','const int mBegin=mt0*16,mEnd=MinI(mt1*16,p.M);')
        # Same low-level load/MMAD sequence; only geometry and publication size differ.
        cons=(HERE/'narrow_consumer.inc').read_text(encoding='utf-8')
        body=prefix+producer+cons+bindings(n,'SmallKProducer<T,TA,TB,128>','NarrowConsumer')
    else:
        prefix='''// BMMS48_BEGIN
namespace bmms48 {
using Plan=bmms83::NativePlan;
constexpr int32_t TM=64,TN=128;
constexpr uint16_t READY=4,FREE=6;
static inline bool Eligible(int B,int M,int N,int K,int cores){
    return B>1&&B<cores&&M<128&&N<256&&K<512&&bmms11d::ResidualEligible(B,M,N,K,cores);
}
static inline Plan MakePlan(int B,int M,int N,int K,int cores){
    Plan p=bmms11d::MakePlan(B,M,N,K,cores);
    p.pM=1;p.pN=1;p.tasks=B;p.blocks=bmms83::MinH(cores,B);return p;
}
static inline uint64_t RingBytes(const Plan& p){return bmms11d::RingBytes(p);}
static inline uint64_t WorkspaceBytes(const Plan& p){return RingBytes(p);}
'''
        body=prefix+(HERE/'batch_consumer.inc').read_text(encoding='utf-8')+bindings(n,'bmms11d::StagedProducer<T,TA,TB>','BatchConsumer')
    h=host(base,'bmms11d').replace('ResidualEligible(','Eligible(').replace('BMMS11D_LAUNCH',f'BMMS{n}_LAUNCH').replace('bmms11d_f16',f'bmms{n}_f16').replace('bmms11d_b16',f'bmms{n}_b16')
    if n==48:h=once(h,'uint8_t* partial=ws+RingBytes(p);','uint8_t* partial=nullptr; // batch-owned epilogue has no partial workspace')
    return body+h+f'\n}} // namespace bmms{n}\n// BMMS{n}_END\n\n'
def main():
    raw=BASE.read_bytes();assert hashlib.sha256(raw).hexdigest()==SHA
    base=raw.decode().replace('\r\n','\n');OUT.mkdir(exist_ok=True)
    (OUT/BASE.name).write_bytes(raw)
    manifest={}
    for n,name in NAMES.items():
        frag=module(n,base).encode()
        anchor=b'extern "C" void run_kernel(GM_ADDR a,const TensorGroupInfo& ia,'
        assert raw.count(anchor)==1
        data=raw.replace(anchor,frag+anchor,1)
        old=(b'        if(bmms25::TryLaunch(a,b,y,p,x.dtype,ta,tb,stream))return;' if n==47 else
             b'    if(bmms11d::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;')
        hook=('        ' if n==47 else '    ')+f'if(bmms{n}::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\r\n'
        assert data.count(old)==1;data=data.replace(old,hook.encode()+old,1)
        assert data.replace(frag,b'',1).replace(hook.encode(),b'',1)==raw
        (OUT/(name+'.asc')).write_bytes(data)
        write(HERE/f'r{n}_extracted.hpp',between(module(n,base),f'// BMMS{n}_BEGIN',f'// BMMS{n}_CPU_END'))
        manifest[name]={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'baseline_recovered_byte_for_byte':True}
    manifest['baseline_sha256']=SHA
    write(OUT/'MANIFEST.json',json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()

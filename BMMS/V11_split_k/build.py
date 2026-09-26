"""R14 -> R23 small-output long-K Cube split-K, K1 ablation, four shape probes."""
from pathlib import Path
import hashlib,json,difflib,shutil
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;OUT=ROOT/'BMMS_V11_R23'
BASE=ROOT/'BMMS_V11_R13_R14/R14_FLEX_SINGLE_WAVE.asc'
BASE_SHA='64eb6eeeb10d2418845d2026b9e9fdd2088d0a3ad1decb0a1bfc46d65cfa78fe'
NAMES={'R23':'R23_SPLIT_K','K1':'R23_K1_CONTROL'}
PROBES={'G01_B1_OFF':'B==1','G02_M64_OFF':'M<=64','G03_N128_OFF':'N<=128','G04_MN4096_OFF':'int64_t(M)*N<=4096'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,s):p.write_text(s,encoding='utf-8',newline='\n')
def once(s,a,b):assert s.count(a)==1,(s.count(a),a[:90]);return s.replace(a,b,1)
def between(s,a,b):i=s.index(a);return s[i:s.index(b,i)]
def producer(base):
    s=between(base,'template<class T,bool TA,bool TB>\nclass StagedProducer {','#ifndef BMMS9_CPU_TEST\ntemplate<class T,bool TA,bool TB>\n__aicore__ inline void Entry(')
    s=once(s,'class StagedProducer {','class Producer {')
    s=once(s,'    int32_t seq=0;\n','')
    s=once(s,'__aicore__ inline void Emit(int group,int batch,int m0,int n0,int mr,int nr){',
                '__aicore__ inline void Emit(int group,int batch,int m0,int n0,int mr,int nr,int kBegin,int kEnd){')
    i=s.index('        // Single L0C:');j=s.index('        auto cc=cBuf.template Get<float>();',i)
    s=s[:i]+'''        const int kCount=(kEnd-kBegin+KB-1)/KB;
        LoadStage(batch,m0,n0,mr,nr,kBegin,bmms83::MinI(KB,kEnd-kBegin),0);
'''+s[j:]
    s=once(s,'const int stage=ki&1,k0=ki*KB,kr=bmms83::MinI(KB,p.K-k0);',
                'const int stage=ki&1,k0=kBegin+ki*KB,kr=bmms83::MinI(KB,kEnd-k0);')
    s=once(s,'const int next=stage^1,nextK=(ki+1)*KB;', 'const int next=stage^1,nextK=kBegin+(ki+1)*KB;')
    s=once(s,'bmms83::MinI(KB,p.K-nextK)', 'bmms83::MinI(KB,kEnd-nextK)')
    s=once(s,'        const int slot=seq&1;\n        if(seq>=2)AscendC::CrossCoreWaitFlag<0x2>(FREE+slot);\n','')
    s=once(s,'ring[(int64_t(group)*2+slot)*TM*TN]','ring[int64_t(group)*TM*TN]')
    s=once(s,'        AscendC::CrossCoreSetFlag<0x2,PIPE_FIX>(READY+slot);\n        ++seq;',
                '        AscendC::CrossCoreSetFlag<0x2,PIPE_FIX>(READY);\n        AscendC::WaitFlag<AscendC::HardEvent::FIX_M>(cFree);')
    s=once(s,'int64_t(p.blocks)*2*TM*TN','int64_t(p.blocks)*TM*TN')
    i=s.index('    __aicore__ inline void Process(){');j=s.index('        for(int s=0;s<2;++s){\n            pipe_->ReleaseEventID',i)
    s=s[:i]+'''    __aicore__ inline void Process(){
        const int group=AscendC::GetBlockIdx(),ks=group%p.splits,tile=group/p.splits;
        const int nt=tile%p.nTiles,mt=(tile/p.nTiles)%p.mTiles,batch=tile/(p.mTiles*p.nTiles);
        const int m0=mt*TM,n0=nt*TN;
        const int units=p.K/32,kBegin=(ks*units/p.splits)*32,kEnd=((ks+1)*units/p.splits)*32;
        Emit(group,batch,m0,n0,bmms83::MinI(TM,p.M-m0),bmms83::MinI(TN,p.N-n0),kBegin,kEnd);
'''+s[j:]
    assert 'seq' not in s and 'FREE' not in s and 'p.pM' not in s
    return s

def fragment(base):
    text='''// R23: one independent Cube task per spatial tile and aligned K shard.
// Host-only selection; immutable partial C; deterministic sum(K) before max(N).
#ifndef BMMS23_SINGLE_K_CONTROL
#define BMMS23_SINGLE_K_CONTROL 0
#endif
namespace bmms23 {
'''+(HERE/'host_plan.asc').read_text(encoding='utf-8')+producer(base)+(HERE/'consumer.asc').read_text(encoding='utf-8')+'''
#ifndef BMMS23_CPU_TEST
template<class T,bool TA,bool TB>
__aicore__ inline void Entry(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ws,Plan p){
    AscendC::TPipe pipe;
    if ASCEND_IS_AIC {Producer<T,TA,TB> op;op.Init(a,b,ws,p,&pipe);op.Process();}
    if ASCEND_IS_AIV {Consumer op;op.Init(ws,y,p,&pipe);op.Process();}
}
#endif
} // namespace bmms23
// BMMS23_CPU_EXTRACT_END

#define BMMS23_KERNEL(NAME,T,TA,TB) \\
__schedmode__(1) __global__ __mix__(1,2) void NAME(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ws,bmms23::Plan p){bmms23::Entry<T,TA,TB>(a,b,y,ws,p);}
'''
    for dt,t in [('f16','half'),('b16','bfloat16_t')]:
        for layout,ta,tb in [('nn','false','false'),('nt','false','true'),('tn','true','false'),('tt','true','true')]:
            text+=f'BMMS23_KERNEL(bmms23_{dt}_{layout},{t},{ta},{tb})\n'
    text+='''#undef BMMS23_KERNEL
namespace bmms23 {
static inline bool TryLaunch(GM_ADDR a,GM_ADDR b,GM_ADDR y,int B,int M,int N,int K,int dtype,bool ta,bool tb,int cores,aclrtStream stream){
    if(!Eligible(B,M,N,K,dtype,cores))return false;
    Plan p=MakePlan(B,M,N,K,cores);
    if(BMMS23_SINGLE_K_CONTROL){p.splits=1;p.blocks=B*p.mTiles*p.nTiles;}
    uint8_t* ws=nullptr;
    if(aclrtMalloc(reinterpret_cast<void**>(&ws),WorkspaceBytes(p),ACL_MEM_MALLOC_HUGE_FIRST)!=ACL_SUCCESS)std::abort();
#define BMMS23_LAUNCH(NAME) NAME<<<p.blocks,nullptr,stream>>>(a,b,y,ws,p)
    if(dtype==1){
        if(!ta&&!tb){BMMS23_LAUNCH(bmms23_f16_nn);}else if(!ta&&tb){BMMS23_LAUNCH(bmms23_f16_nt);}
        else if(ta&&!tb){BMMS23_LAUNCH(bmms23_f16_tn);}else{BMMS23_LAUNCH(bmms23_f16_tt);}
    }else{
        if(!ta&&!tb){BMMS23_LAUNCH(bmms23_b16_nn);}else if(!ta&&tb){BMMS23_LAUNCH(bmms23_b16_nt);}
        else if(ta&&!tb){BMMS23_LAUNCH(bmms23_b16_tn);}else{BMMS23_LAUNCH(bmms23_b16_tt);}
    }
#undef BMMS23_LAUNCH
    if(aclrtSynchronizeStream(stream)!=ACL_SUCCESS)std::abort();
    if(aclrtFree(ws)!=ACL_SUCCESS)std::abort();return true;
}
} // namespace bmms23
'''
    return text

MARK='extern "C" void run_kernel(GM_ADDR a,const TensorGroupInfo& ia,'
HOOK='    if(bmms11d::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;'
CALL='    if(bmms23::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;'
PROBE_HOOK='static inline bool ResidualEligible(int32_t B,int32_t M,int32_t N,int32_t K,int32_t cores){\n'
def probe_line(predicate):
    return '    if(M>=16&&M<128&&N>=16&&N<256&&K>=4096&&K<=8192&&M%16==0&&N%16==0&&K%32==0&&('+predicate+'))return false;\n'
def verify():
    assert sha(BASE)==BASE_SHA and sha(OUT/'R14_CONTROL.asc')==BASE_SHA
    base=BASE.read_text(encoding='utf-8');frag=fragment(base)
    assert frag==(HERE/'split_k_fragment.asc').read_text(encoding='utf-8')
    for version,name in NAMES.items():
        source=(OUT/(name+'.asc')).read_text(encoding='utf-8')
        if version=='K1':source=once(source,'#define BMMS23_SINGLE_K_CONTROL 1\n','')
        restored=once(once(source,frag+'\n',''),CALL+'\n','')
        assert restored.split('\n',1)[1]==base.split('\n',1)[1]
    for name,predicate in PROBES.items():
        source=(OUT/(name+'.asc')).read_text(encoding='utf-8')
        assert once(source,probe_line(predicate),'').split('\n',1)[1]==base.split('\n',1)[1]
    return {'R14_restored_outside_fragment_and_host_hook':True,'eight_fixed_dtype_layout_entries':True,
            'K1_changes_only_split_count_after_same_guard':True,'four_probes_change_only_R03_eligibility':True,
            'R22_not_inherited':True}
def main():
    assert sha(BASE)==BASE_SHA;OUT.mkdir(exist_ok=True);shutil.copyfile(BASE,OUT/'R14_CONTROL.asc')
    base=BASE.read_text(encoding='utf-8');frag=fragment(base);write(HERE/'split_k_fragment.asc',frag)
    for version,name in NAMES.items():
        source=once(once(base,MARK,frag+'\n'+MARK),HOOK,CALL+'\n'+HOOK)
        if version=='K1':source=once(source,frag,'#define BMMS23_SINGLE_K_CONTROL 1\n'+frag)
        source=once(source,source.split('\n',1)[0],f'// {name}: R14-based small-output long-K Cube route; pending CANN/NPU validation.')
        write(OUT/(name+'.asc'),source)
        write(HERE/(name+'.diff'),''.join(difflib.unified_diff(base.splitlines(True),source.splitlines(True),fromfile='R14',tofile=name)))
    for name,predicate in PROBES.items():
        source=once(base,PROBE_HOOK,PROBE_HOOK+probe_line(predicate))
        source=once(source,source.split('\n',1)[0],f'// {name}: diagnostic R03 bypass within reported small-M/N long-K domain; not an optimization.')
        write(OUT/(name+'.asc'),source)
    report={'base_sha256':BASE_SHA,'files':[{'file':p.name,'sha256':sha(p)} for p in sorted(OUT.glob('*.asc'))],
            'composition':verify(),'cann_compiled_locally':False,'npu_tested_locally':False}
    write(OUT/'MANIFEST.json',json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()

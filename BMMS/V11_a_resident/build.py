"""Three independent R14 descendants: two existing coverage edits, one resident-A experiment."""
from pathlib import Path
import difflib,hashlib,importlib.util,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;OUT=ROOT/'BMMS_V11_R17_R18_R19'
BASE=ROOT/'BMMS_V11_R13_R14/R14_FLEX_SINGLE_WAVE.asc'
BASE_SHA='64eb6eeeb10d2418845d2026b9e9fdd2088d0a3ad1decb0a1bfc46d65cfa78fe'
OLD_MACRO=ROOT/'V11_flexible_grid/R14_macro_fragment.asc'
OLD_RESIDUAL=ROOT/'V11_merge/residual_dense_fragment.asc'
NAMES={'R17':'R17_R14_K32_GAPS','R18':'R18_R14_K16_TAILS','R19':'R19_R14_A_RESIDENT'}
spec=importlib.util.spec_from_file_location('kcoverage_builder',ROOT/'V11_k_coverage/build.py')
coverage=importlib.util.module_from_spec(spec);spec.loader.exec_module(coverage)
sha=coverage.sha;write=coverage.write;once=coverage.once;between=coverage.between;function=coverage.function
PRODUCER_START='template<class T,bool TA,bool TB>\nclass ReuseProducer {'
CONSUMER_START='class RowMaxConsumer {'

def resident_producer(old):
    s=between(old,PRODUCER_START,CONSUMER_START)
    s=once(s,PRODUCER_START,'template<class T,bool TA,bool TB,int RK>\nclass ResidentAProducer {\n    static_assert(RK==256||RK==512,"resident A only supports K256/K512");')
    s=once(s,'    int32_t seq=0;bool cPending=false;',
        '    AscendC::TEventID aReady,aFree;\n    int32_t seq=0;bool cPending=false;')
    oldA=between(s,'        auto aa=a1Buf.template Get<T>()[s*AM*K1];','        AscendC::Nd2NzParams qb{};')
    s=once(s,oldA,'        auto bb=b1Buf.template Get<T>()[s*K1*BN];\n')
    s=once(s,'    __aicore__ inline void LoadStage(','''    // Complete A belongs to this (batch, M macro, N shard), not to a B K1 panel.
    __aicore__ inline void LoadResidentA(int batch,int m0,int ar){
        auto aa=a1Buf.template Get<T>();
        AscendC::Nd2NzParams qa{};qa.ndNum=1;
        qa.nValue=TA?RK:ar;qa.dValue=TA?ar:RK;
        qa.srcDValue=TA?p.M:p.K;qa.dstNzC0Stride=TA?RK:ar;qa.dstNzNStride=1;
        const int64_t ai=int64_t(batch)*p.M*p.K+(TA?m0:int64_t(m0)*p.K);
        AscendC::DataCopy(aa,a[ai],qa);
        AscendC::SetFlag<AscendC::HardEvent::MTE2_MTE1>(aReady);
        AscendC::WaitFlag<AscendC::HardEvent::MTE2_MTE1>(aReady);
    }

    // Only B uses the ping-pong K1 slots. A is retained across the entire N scan.
    __aicore__ inline void LoadStage(''')
    s=once(s,'LoadL0(int ar,int br,int kr1,int kk,int kr0,int s1,int s0)',
        'LoadL0(int ar,int br,int kr1,int kBase,int kk,int kr0,int s1,int s0)')
    s=once(s,'auto sa=a1Buf.template Get<T>()[s1*AM*K1];','auto sa=a1Buf.template Get<T>();')
    s=once(s,'const int off=TA?(mo/16+i)*kr1*16+kk*16:(kk/16)*ar*16+(mo+i*16)*16;',
        'const int ak=kBase+kk;\n                const int off=TA?(mo/16+i)*RK*16+ak*16:(ak/16)*ar*16+(mo+i*16)*16;')
    s=once(s,'LoadL0(ar,br,kr1,kk,kr0,s1,s0);','LoadL0(ar,br,kr1,kBase,kk,kr0,s1,s0);')
    s=once(s,'// Free L1 only after the last K0 slice has read BOTH shared operands.',
        '// Recycle only the B K1 slot here; complete A remains live for the N scan.')
    s=once(s,'        p=plan;pipe_=pipe;',
        '''        p=plan;pipe_=pipe;
        aReady=pipe->AllocEventID<AscendC::HardEvent::MTE2_MTE1>();
        aFree=pipe->AllocEventID<AscendC::HardEvent::MTE1_MTE2>();''')
    s=once(s,'pipe->InitBuffer(a1Buf,2*AM*K1*sizeof(T));','pipe->InitBuffer(a1Buf,AM*RK*sizeof(T));')
    s=once(s,'''            for(int m0=mBegin;m0<mEnd;m0+=AM)for(int n0=nBegin;n0<nEnd;n0+=BN)
                Macro(group,batch,m0,n0,MinI(AM,mEnd-m0),MinI(BN,nEnd-n0));''',
        '''            for(int m0=mBegin;m0<mEnd;m0+=AM){
                const int ar=MinI(AM,mEnd-m0);
                LoadResidentA(batch,m0,ar);
                for(int n0=nBegin;n0<nEnd;n0+=BN)
                    Macro(group,batch,m0,n0,ar,MinI(BN,nEnd-n0));
                // Fence the whole N scan before this A storage can be overwritten.
                AscendC::SetFlag<AscendC::HardEvent::MTE1_MTE2>(aFree);
                AscendC::WaitFlag<AscendC::HardEvent::MTE1_MTE2>(aFree);
            }''')
    s=once(s,'        pipe_->ReleaseEventID<AscendC::HardEvent::M_FIX>(cReady);',
        '''        pipe_->ReleaseEventID<AscendC::HardEvent::MTE2_MTE1>(aReady);
        pipe_->ReleaseEventID<AscendC::HardEvent::MTE1_MTE2>(aFree);
        pipe_->ReleaseEventID<AscendC::HardEvent::M_FIX>(cReady);''')
    return s

def launch_block(stem):
    return '''    if(dtype==1){
        if(!ta&&!tb){BMMS11R2_LAUNCH(STEM_f16_nn);}else if(!ta&&tb){BMMS11R2_LAUNCH(STEM_f16_nt);}
        else if(ta&&!tb){BMMS11R2_LAUNCH(STEM_f16_tn);}else{BMMS11R2_LAUNCH(STEM_f16_tt);}
    }else{
        if(!ta&&!tb){BMMS11R2_LAUNCH(STEM_b16_nn);}else if(!ta&&tb){BMMS11R2_LAUNCH(STEM_b16_nt);}
        else if(ta&&!tb){BMMS11R2_LAUNCH(STEM_b16_tn);}else{BMMS11R2_LAUNCH(STEM_b16_tt);}
    }
'''.replace('STEM',stem)

def resident_fragment(old):
    producer=resident_producer(old)
    selector='''// Require at least two N macro tiles in EVERY task. Mixed 1/2-tile shards keep R14.
static inline bool UseResidentA(const Plan& p){
    return (p.K==256||p.K==512)&&p.pN>0&&p.nTiles>=2*p.pN;
}

'''
    s=once(old,CONSUMER_START,selector+producer+CONSUMER_START)
    entry='''template<class T,bool TA,bool TB,int RK>
__aicore__ inline void ResidentEntry(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ring,GM_ADDR partial,Plan p){
    AscendC::TPipe pipe;
    if ASCEND_IS_AIC {ResidentAProducer<T,TA,TB,RK> op;op.Init(a,b,ring,p,&pipe);op.Process();}
    if ASCEND_IS_AIV {RowMaxConsumer op;op.Init(ring,partial,y,p,&pipe);op.Process();}
}
'''
    s=once(s,'#endif\n} // namespace bmms11r2\n// BMMS11R2_CPU_EXTRACT_END',entry+'#endif\n} // namespace bmms11r2\n// BMMS11R2_CPU_EXTRACT_END')
    kernels='''#define BMMS19_KERNEL(NAME,T,TA,TB,RK) \\
__schedmode__(1) __global__ __mix__(1,2) void NAME(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ring,GM_ADDR part,bmms11r2::Plan p){bmms11r2::ResidentEntry<T,TA,TB,RK>(a,b,y,ring,part,p);}
'''
    for k in [256,512]:
        for tag,t in [('f16','half'),('b16','bfloat16_t')]:
            for layout,ta,tb in [('nn','false','false'),('nt','false','true'),('tn','true','false'),('tt','true','true')]:
                kernels+=f'BMMS19_KERNEL(bmms19_k{k}_{tag}_{layout},{t},{ta},{tb},{k})\n'
    kernels+='#undef BMMS19_KERNEL\n'
    s=once(s,'#undef BMMS11R2_KERNEL\nnamespace bmms11r2 {','#undef BMMS11R2_KERNEL\n'+kernels+'namespace bmms11r2 {')
    oldLaunch=launch_block('bmms11r2')
    newLaunch='    if(UseResidentA(p)){\n        if(K==256){\n'+launch_block('bmms19_k256')+'        }else{\n'+launch_block('bmms19_k512')+'        }\n    }else{\n'+oldLaunch+'    }\n'
    s=once(s,oldLaunch,newLaunch)
    return s

def fragments(version):
    m=OLD_MACRO.read_text(encoding='utf-8');d=OLD_RESIDUAL.read_text(encoding='utf-8')
    if version=='R14':return m,d
    if version in ['R17','R18']:
        oldCoverageMacro=coverage.OLD_MACRO.read_text(encoding='utf-8')
        cm,cd=coverage.fragments('R15' if version=='R17' else 'R16')
        oldGuard=function(oldCoverageMacro,'static inline bool Eligible(')
        newGuard=function(cm,'static inline bool Eligible(')
        return once(m,oldGuard,newGuard),cd
    assert version=='R19';return resident_fragment(m),d

def verify():
    assert sha(BASE)==BASE_SHA and sha(OUT/'R14_CONTROL.asc')==BASE_SHA
    oldM,oldD=fragments('R14');original=BASE.read_text(encoding='utf-8')
    for v,name in NAMES.items():
        m,d=fragments(v);s=(OUT/(name+'.asc')).read_text(encoding='utf-8')
        assert m==(HERE/(v+'_macro_fragment.asc')).read_text(encoding='utf-8')
        assert d==(HERE/(v+'_residual_fragment.asc')).read_text(encoding='utf-8')
        assert once(once(s,m,oldM),d,oldD).split('\n',1)[1]==original.split('\n',1)[1]
        # Every descendant keeps R14's planner, consumer, original producer and ring/workspace functions.
        assert between(m,'// Closed-form peak','static inline uint64_t RingBytes(')==between(oldM,'// Closed-form peak','static inline uint64_t RingBytes(')
        assert between(m,PRODUCER_START,CONSUMER_START).startswith(between(oldM,PRODUCER_START,CONSUMER_START))
        assert between(m,CONSUMER_START,'#ifndef BMMS11R2_CPU_TEST')==between(oldM,CONSUMER_START,'#ifndef BMMS11R2_CPU_TEST')
        if v=='R19':
            assert d==oldD and function(m,'static inline bool Eligible(')==function(oldM,'static inline bool Eligible(')
            producer=resident_producer(oldM)
            for a,b in [('                auto aa=a2Buf.template Get<T>()[s0*AM*K0];','        for(int s=0;s<MinI(2,kCount);'),
                        ('        const int macroSlot=seq&1;','public:')]:
                assert between(producer,a,b)==between(between(oldM,PRODUCER_START,CONSUMER_START),a,b)
        else:assert m[m.index('// Closed-form peak'):]==oldM[oldM.index('// Closed-form peak'):]
    return {'independent_R14_descendants':True,'R17_R18_rebase_existing_R15_R16_guards':True,
        'R19_no_K_coverage_extension':True,'R14_planners_preserved':True,'consumers_and_ring_protocols_preserved':True,
        'original_producer_fallback_preserved':True,'R19_MMAD_sequence_and_output_publish_body_preserved':True,
        'R19_gate':'K in {256,512} and floor(nTiles/pN) >= 2','input_plan_source_archived':True}

def main():
    assert sha(BASE)==BASE_SHA;OUT.mkdir(exist_ok=True)
    (OUT/'R14_CONTROL.asc').write_bytes(BASE.read_bytes());original=BASE.read_text(encoding='utf-8');oldM,oldD=fragments('R14');rows=[]
    for v,name in NAMES.items():
        m,d=fragments(v);write(HERE/(v+'_macro_fragment.asc'),m);write(HERE/(v+'_residual_fragment.asc'),d)
        s=once(once(original,oldM,m),oldD,d)
        s=once(s,s.split('\n',1)[0],'// '+name+': independent R14 descendant; pending platform validation.')
        p=OUT/(name+'.asc');write(p,s)
        write(HERE/(name+'.diff'),''.join(difflib.unified_diff(original.splitlines(True),s.splitlines(True),fromfile='R14',tofile=name)))
        rows.append({'version':v,'file':p.name,'sha256':sha(p),'platform_result_received':False})
    write(HERE/'resident_producer.asc',resident_producer(oldM))
    plan=Path('C:/Users/cc/Downloads/BMMS_R14_技术审计与下一轮突破_20260926.md')
    frozen=HERE/'INPUT_PLAN.md'
    if not frozen.exists():frozen.write_bytes(plan.read_bytes())
    if plan.exists():assert frozen.read_bytes()==plan.read_bytes()
    manifest={'base':BASE.relative_to(ROOT).as_posix(),'base_sha256':BASE_SHA,'control':{'file':'R14_CONTROL.asc','sha256':BASE_SHA},
        'variants':rows,'proof':verify(),'input_plan_sha256':sha(frozen),'cann_compiled_locally':False,'npu_tested_locally':False,
        'known_numerical_limitations_remain':True}
    write(OUT/'MANIFEST.json',json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()

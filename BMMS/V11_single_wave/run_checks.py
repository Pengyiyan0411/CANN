"""Check R10/R11/R12 source, short-wave plans, parallel reduction ownership and fault detection."""
from pathlib import Path
import importlib.util,json,os,shutil,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;BUILD=HERE/'cpu_build'
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m
build=load('single_wave_build',HERE/'build.py')
prior=load('recovery_checks',ROOT/'V11_recovery/run_checks.py')
prior.BUILD=prior.prior.BUILD=prior.prior.prior.BUILD=prior.prior.prior.parent.BUILD=prior.prior.prior.parent.previous.BUILD=prior.prior.prior.parent.previous.parent.BUILD=BUILD
once=build.once;call=prior.call
def prepare(version):
    prior.prepare('R10')
    source=(build.BASE if version=='R10' else build.OUT/(build.NAMES[version]+'.asc')).read_text(encoding='utf-8')
    frag=(ROOT/'V11_recovery/one_wave_macro_fragment.asc' if version=='R10' else HERE/('expanded_macro_fragment.asc' if version=='R11' else 'parallel_macro_fragment.asc')).read_text(encoding='utf-8')
    assert frag in source
    extracted=prior.prior.prior.parent.previous.parent.extract(frag,'// BMMS11R2_CPU_EXTRACT_END')
    if version!='R12':
        # An isolated reference helper containing the original final-stage body verbatim.
        c=build.consumer(extracted);tail=build.old_finish(frag)
        helper='    __aicore__ inline void FinishReduction(){\n        const int worker=AscendC::GetBlockIdx();\n'+tail+'    }\n'
        c=once(c,'    __aicore__ inline void Process(){',helper+'    __aicore__ inline void Process(){')
        extracted=once(extracted,build.consumer(extracted),c)
    build.write(BUILD/'ring_extracted.hpp',extracted)
    path=BUILD/'cpu_shim.hpp';s=path.read_text(encoding='utf-8')
    audit=(HERE/'reduction_audit.hpp').read_text(encoding='utf-8')
    s=s.replace('namespace AscendC {',audit+'\nnamespace AscendC {',1)
    s=once(s,'        if(!r->input){size_t j=((uintptr_t)(p+i)-r->start)/4;',
        '        ReductionAudit::read((uintptr_t)(p+i));\n        if(!r->input){size_t j=((uintptr_t)(p+i)-r->start)/4;')
    s=once(s,'        int prev=r->writer[j].load();',
        '        ReductionAudit::write((uintptr_t)(p+i));\n        int prev=r->writer[j].load();')
    build.write(path,s)
def harness(version):
    s=prior.harness('R10')
    s='#define HAS_MERGE_SCRATCH '+('1' if version=='R12' else '0')+'\n'+s
    if version=='R11':
        s=once(s,'''        Mock::need(p.mTiles==r2.mTiles&&p.nTiles==r2.nTiles&&p.tasks==r2.tasks&&p.blocks==r2.blocks,
            "single-wave plan altered launch/task count");
        if(p.pM!=r2.pM||p.pN!=r2.pN){
            Mock::need(p.tasks==p.blocks&&r2.tasks==r2.B*r2.pM*r2.pN,"changed multi-wave plan");
            auto a=bmms11r2::SingleWavePeak(p),b=bmms11r2::SingleWavePeak(r2);
            Mock::need(8*b.tiles<=7*a.tiles&&8*b.cells<=7*a.cells&&8*b.input<=7*a.input,"grid margin violated");
        }''', '''        auto base=bmms11r2::MakeR10Plan(B,M,N,K,cores);
        Mock::need(base.blocks==r2.blocks&&base.mTiles==r2.mTiles&&base.nTiles==r2.nTiles,"changed launch/domain");
        if(base.pM!=r2.pM||base.pN!=r2.pN){
            Mock::need(base.tasks>base.blocks&&r2.tasks==r2.blocks&&r2.tasks==B*r2.pM*r2.pN,"invalid wave removal");
            auto a=bmms11r2::ExistingPeak(base),b=bmms11r2::SingleWavePeak(r2);
            Mock::need(8*b.tiles<=7*a.tiles&&8*b.cells<=7*a.cells&&8*b.input<=7*a.input,"new grid margin violated");
        }else Mock::need(base.tasks==r2.tasks,"task count changed without grid change");''')
    s=once(s,'    Mock::Context ctx(2*p.blocks);Mock::Flags flags(p.blocks);',
        '''    Mock::Context ctx(2*p.blocks);Mock::Flags flags(p.blocks);
    ReductionAudit::State reductionAudit(part.data(),B,M,p.pN,2*p.blocks,HAS_MERGE_SCRATCH&&useMacro);
    ReductionAudit::active=useMacro?&reductionAudit:nullptr;''')
    s=once(s,'        flags.drained();ringAudit.drained();RingAudit::active=nullptr;',
        '''        flags.drained();ringAudit.drained();RingAudit::active=nullptr;
        ReductionAudit::active=nullptr;
        if(useMacro)reductionAudit.check(HAS_MERGE_SCRATCH&&p.pN>=4&&M>=1024);''')
    s=once(s,'int main(){try{',(HERE/'reduction_checks.cpp.in').read_text(encoding='utf-8')+'\nint main(){try{')
    s=once(s,'    guards();', '''    std::string reduction=reductionChecks();
#if defined(NEGATIVE_MERGE_BARRIER) || defined(NEGATIVE_MERGE_SHARD)
    return 7;
#endif
    guards();''')
    s=once(s,'    std::ostringstream fixtures;', '''    for(int rev=0;rev<2;++rev){
        // R11 changes the old 4x2 grid (8 tasks) to 2x3 (6 tasks).
        dense<half,false,false>(1,512,768,256,6,0,rev);
        dense<bfloat16_t,true,true>(1,512,768,256,6,1,rev);
        // The actual R10 plan has pN=4 here, activating R12's parallel merge.
        dense<half,false,true>(1,1024,1024,256,32,0,rev);
        dense<bfloat16_t,true,false>(1,1024,1024,256,32,1,rev);
    }
    std::ostringstream fixtures;''')
    s=once(s,'<<",\\\"max_abs\\\":"<<maxError',
        '<<",\\\"reduction_checks\\\":"<<reduction<<",\\\"max_abs\\\":"<<maxError')
    return s
def grid_check(compiler):
    template=(ROOT/'V11_grid_packets/grid_checks.cpp.in').read_text(encoding='utf-8');parts=[]
    for ns,path in [('baseline',ROOT/'V11_recovery/one_wave_macro_fragment.asc'),('candidate',HERE/'expanded_macro_fragment.asc')]:
        f=path.read_text(encoding='utf-8');b=build.between(f,'namespace bmms11r2 {','static inline uint64_t RingBytes(')
        parts.append(b.replace('namespace bmms11r2 {','namespace '+ns+' {',1)+'}\n')
    s=once(template,'// INSERT_PLANS','\n'.join(parts))
    s=once(s,'for(int cores:{1,2,3,8,20,32,64})for(int tail:{0,16})',
        'for(int cores:{1,2,3,6,8,20,32,64})for(int tail:{0,16,48,112})')
    s=once(s,'int M=mt*128-(tail?112:0),N=nt*256-(tail?240:0);',
        'int M=mt*128-tail,N=nt*256-(tail==112?240:tail);')
    s=once(s,'''        auto a=walk(old),b=walk(p);auto pred=candidate::PeakForGrid(p);
        need(pred.tiles==b.tiles&&pred.cells==b.cells&&pred.input==b.input,"cost disagrees with device traversal");''',
        '''        auto a=walk(old),b=walk(p);auto pred=candidate::ExistingPeak(p);
        need(pred.tiles==b.tiles&&pred.cells==b.cells&&pred.input==b.input,"existing-grid cost mismatch");
        need(p.blocks==old.blocks,"changed launched core count");
        if(old.tasks==old.blocks)need(p.pM==old.pM&&p.pN==old.pN&&p.tasks==old.tasks,"lost R10 single-wave decision");
        if(p.tasks==p.blocks){auto closed=candidate::SingleWavePeak(p);
            need(closed.tiles==b.tiles&&closed.cells==b.cells&&closed.input==b.input,"candidate closed form mismatch");}''')
    s=once(s,'            need(b.tiles*8<=a.tiles*7',
        '            need(p.tasks==p.blocks&&old.tasks>old.blocks&&old.tasks<2*cores,"invalid wave transition");\n            need(b.tiles*8<=a.tiles*7')
    s=once(s,'{{1,384,768,256,5},{1,1024,1024,256,20},',
        '{{1,512,768,256,6},{1,384,768,256,5},{1,1024,1024,256,20},')
    build.write(BUILD/'grid_checks.cpp',s);exe=BUILD/'grid_checks.exe'
    call([compiler,'-std=c++20','-O2','grid_checks.cpp','-o',str(exe)],'grid_compile')
    data=json.loads(call([str(exe)],'grid_run').stdout);assert data['checked']==6758 and data['changed']>0
    build.write(HERE/'GRID_CHECKS.json',json.dumps(data,indent=2)+'\n');print('Grid: '+json.dumps(data),flush=True);return data
def main():
    build.verify();prepare('R10');compiler=shutil.which(os.environ.get('CXX','g++'));assert compiler
    grid=grid_check(compiler);runs={}
    args=[compiler,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-pthread','-DCHECK_R01=1','-DCHECK_R04=1','source_checks.cpp']
    for version in ['R10','R11','R12']:
        prepare(version);build.write(BUILD/'source_checks.cpp',harness(version));exe=BUILD/(version+'.exe')
        call(args+['-o',str(exe)],version+'_compile');data=json.loads(call([str(exe)],version+'_run').stdout);runs[version]=data
        assert data['source_runs']==452 and data['repeat_pairs']==226,(data['source_runs'],data['repeat_pairs'])
        assert data['strict_misses']==data['combined_misses']==0 and data['known_precision_limitations']==3
        assert data['reduction_checks']['checked']==22
        assert data['reduction_checks']['parallel_cases']==(14 if version=='R12' else 0)
        build.write(HERE/(version+'_CPU_RESULT.json'),json.dumps(data,indent=2)+'\n')
        print(version+': '+json.dumps({k:v for k,v in data.items() if k not in ['output_bits','reduction_checks']}),flush=True)
    assert runs['R10']['output_bits']==runs['R11']['output_bits']==runs['R12']['output_bits']
    old=json.loads((ROOT/'V11_recovery/R10_CPU_RESULT.json').read_text(encoding='utf-8'))
    for key,bits in old['output_bits'].items():assert runs['R10']['output_bits'][key]==bits
    assert runs['R10']['peak_arena_bytes']==runs['R11']['peak_arena_bytes']==runs['R12']['peak_arena_bytes']
    for fixture in ['macro_wide','native_wide','residual_wide']:
        assert runs['R10']['fixtures'][fixture]==runs['R11']['fixtures'][fixture]==runs['R12']['fixtures'][fixture]
    negatives={}
    for old,new,define,error in [
        ('AscendC::SyncAll<true>(); // MERGE_COMPLETE_BARRIER','// Negative control: missing merge barrier.',
         'NEGATIVE_MERGE_BARRIER','merged rows read before completion barrier'),
        ('for(int ns=1;ns<p.pN;++ns){\n                    AscendC::DataCopyPad(tmp,',
         'for(int ns=1;ns<p.pN-1;++ns){\n                    AscendC::DataCopyPad(tmp,',
         'NEGATIVE_MERGE_SHARD','N-merge reference mismatch')]:
        prepare('R12');build.write(BUILD/'source_checks.cpp',harness('R12'));path=BUILD/'ring_extracted.hpp'
        good=path.read_text(encoding='utf-8');build.write(path,once(good,old,new));exe=BUILD/(define+'.exe')
        try:
            call(args+['-D'+define+'=1','-o',str(exe)],define+'_compile')
            result=call([str(exe)],define+'_run',failure=error)
        finally:build.write(path,good)
        negatives[define]={'rejected':True,'exit_code':result.returncode,'stderr':result.stderr.strip()}
    previous=json.loads((ROOT/'V11_recovery/CHECKS.json').read_text(encoding='utf-8'));artifacts=dict(previous['artifacts'])
    for path,digest in artifacts.items():assert build.sha(ROOT/path)==digest,path
    for path in [HERE/'build.py',Path(__file__),HERE/'expanded_plan_tail.asc',HERE/'expanded_plan.asc',
                 HERE/'parallel_finish.asc',HERE/'expanded_macro_fragment.asc',HERE/'parallel_macro_fragment.asc',
                 HERE/'reduction_audit.hpp',HERE/'reduction_checks.cpp.in',ROOT/'V11_recovery/run_checks.py',
                 ROOT/'V11_recovery/R10_CPU_RESULT.json']:
        artifacts[path.relative_to(ROOT).as_posix()]=build.sha(path)
    report={'scope':'actual-source CPU storage/event and reduction ownership checks; not NPU simulation or timing',
            'sources':{p.name:build.sha(p) for p in build.OUT.glob('*.asc')},'composition':build.verify(),
            'ordinary_outputs_equal_bitwise':True,'known_numerical_limitations_remain':True,
            'negative_controls':negatives,'grid_checks':grid,
            'runs':{k:{kk:vv for kk,vv in v.items() if kk!='output_bits'} for k,v in runs.items()},
            'R10_R11_isolated_helpers_copy_original_tail_verbatim':True,
            'cann_compiled_locally':False,'npu_tested_locally':False,'artifacts':artifacts}
    for path in [HERE/'CHECKS.json',build.OUT/'CPU_CHECKS.json']:build.write(path,json.dumps(report,indent=2)+'\n')
    print('Source outputs, wave coverage, reduction ownership and both fault injections passed.',flush=True)
if __name__=='__main__':main()

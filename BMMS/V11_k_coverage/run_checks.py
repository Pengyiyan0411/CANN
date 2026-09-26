"""Execute the two changed guards with real producer/consumer source, including new K tails."""
from pathlib import Path
import importlib.util,json,os,shutil,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;BUILD=HERE/'cpu_build'
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m
build=load('k_coverage_build',HERE/'build.py')
prior=load('single_wave_checks',ROOT/'V11_single_wave/run_checks.py')
def redirect(m,seen=None):
    seen=set() if seen is None else seen
    if id(m) in seen:return
    seen.add(id(m))
    if hasattr(m,'BUILD'):m.BUILD=BUILD
    for name in ['prior','parent','previous']:
        if hasattr(m,name):redirect(getattr(m,name),seen)
redirect(prior)
once=build.once;call=prior.call
def prepare(version):
    prior.prepare('R11')
    source=(build.OUT/(build.NAMES[version]+'.asc')).read_text(encoding='utf-8')
    macro,residual=build.fragments(version);assert macro in source and residual in source
    extract=prior.prior.prior.prior.parent.previous.parent.extract
    s=extract(macro,'// BMMS11R2_CPU_EXTRACT_END');c=prior.build.consumer(s)
    helper='    __aicore__ inline void FinishReduction(){\n        const int worker=AscendC::GetBlockIdx();\n'+prior.build.old_finish(macro)+'    }\n'
    c=once(c,'    __aicore__ inline void Process(){',helper+'    __aicore__ inline void Process(){')
    build.write(BUILD/'ring_extracted.hpp',once(s,prior.build.consumer(s),c))
    build.write(BUILD/'residual_extracted.hpp',extract(residual,'// BMMS9_CPU_EXTRACT_END'))
    family=build.between(source,'enum class Family : int32_t {\n    Dot=0,','static inline int32_t MinH(')
    dispatch='namespace bmmmaxsum_v43 {\n'+build.function(source,'static inline bool UseTiny(int32_t M, int32_t N, int32_t K)')+'\n}\n'
    dispatch+='namespace bmms8 {\n'+family+build.function(source,'static inline bool IsFixedSmallK(')+'\n'+build.function(source,'static inline Family Classify(')+'\n}\n'
    build.write(BUILD/'dispatch_extracted.hpp',dispatch)
def harness(version):
    s='#define K_VARIANT '+version[1:]+'\n'+prior.harness('R11')
    s=once(s,'#include "residual_extracted.hpp"','#include "residual_extracted.hpp"\n#include "dispatch_extracted.hpp"')
    s=once(s,'    bool useMacro=bmms11r2::Eligible(B,M,N,K,cores);',
        '''    auto family=bmms8::Classify(B,M,N,K,TA,TB);
    bool protectedFamily=family==bmms8::Family::Resident||family==bmms8::Family::Tiny;
    bool useMacro=bmms11r2::Eligible(B,M,N,K,cores)&&!protectedFamily;''')
    s=once(s,'useSmall||bmms11d::ResidualEligible(B,M,N,K,cores)',
        'useSmall||(bmms11d::ResidualEligible(B,M,N,K,cores)&&!protectedFamily)')
    s=once(s,'int main(){try{',(HERE/'domain_checks.cpp.in').read_text(encoding='utf-8')+'\nint main(){try{\n'+'''
    domainChecksAll();
#ifdef NEGATIVE_GUARD
    return 7;
#endif
#ifdef NEGATIVE_KTAIL
    dense<half,false,false>(1,16,32,48,1,0,false);
    if(strictMisses)throw std::runtime_error("K-tail reference mismatch");
    return 7;
#endif
''')
    s=once(s,'    std::ostringstream fixtures;',(HERE/'new_domain_cases.cpp.in').read_text(encoding='utf-8')+'\n    std::ostringstream fixtures;')
    s=once(s,'<<",\\\"max_abs\\\":"<<maxError',
        '<<",\\\"domain_checks\\\":"<<domainChecks<<",\\\"new_macro_domain_checks\\\":"<<newMacroChecks<<",\\\"new_residual_domain_checks\\\":"<<newResidualChecks<<",\\\"protected_family_checks\\\":"<<protectedChecks<<",\\\"max_abs\\\":"<<maxError')
    return s
def main():
    build.verify();BUILD.mkdir(exist_ok=True);compiler=shutil.which(os.environ.get('CXX','g++'));assert compiler
    previous=json.loads((ROOT/'V11_single_wave/CHECKS.json').read_text(encoding='utf-8'))
    assert previous['sources'][build.BASE.name]==build.BASE_SHA
    old=json.loads((ROOT/'V11_single_wave/R11_CPU_RESULT.json').read_text(encoding='utf-8'))
    args=[compiler,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-pthread','-DCHECK_R01=1','-DCHECK_R04=1','source_checks.cpp']
    runs={}
    for version,added in [('R15',176),('R16',288)]:
        prepare(version);build.write(BUILD/'source_checks.cpp',harness(version));exe=BUILD/(version+'.exe')
        call(args+['-o',str(exe)],version+'_compile');data=json.loads(call([str(exe)],version+'_run').stdout);runs[version]=data
        assert data['source_runs']==452+added and data['repeat_pairs']==226+added//2,(version,data['source_runs'],data['repeat_pairs'])
        assert data['strict_misses']==data['combined_misses']==0 and data['known_precision_limitations']==3
        for key,bits in old['output_bits'].items():assert data['output_bits'][key]==bits,(version,key)
        for key in ['peak_arena_bytes','fixtures','mixed_route_sequence','mixed_ring_bytes_per_group','mixed_ready_packets']:
            assert data[key]==old[key],(version,key)
        build.write(HERE/(version+'_CPU_RESULT.json'),json.dumps(data,indent=2)+'\n')
        print(version+': '+json.dumps({k:v for k,v in data.items() if k not in ['output_bits','reduction_checks']}),flush=True)
    negatives={}
    for version,filename,a,b,define,error in [
        ('R15','ring_extracted.hpp','K>=96&&K!=128&&K%32==0','K>=96&&K%32==0','NEGATIVE_GUARD','K guard domain mismatch'),
        ('R16','residual_extracted.hpp','q.k=kr;','q.k=kr/32*32;','NEGATIVE_KTAIL','K-tail reference mismatch')]:
        prepare(version);build.write(BUILD/'source_checks.cpp',harness(version));path=BUILD/filename;good=path.read_text(encoding='utf-8')
        build.write(path,once(good,a,b));exe=BUILD/(define+'.exe')
        try:
            call(args+['-D'+define+'=1','-o',str(exe)],define+'_compile')
            run=call([str(exe)],define+'_run',failure=error)
        finally:build.write(path,good)
        negatives[define]={'rejected':True,'exit_code':run.returncode,'stderr':run.stderr.strip()}
    artifacts=dict(previous['artifacts'])
    for rel,digest in artifacts.items():assert build.sha(ROOT/rel)==digest,rel
    for path in [HERE/'build.py',Path(__file__),HERE/'domain_checks.cpp.in',HERE/'new_domain_cases.cpp.in',
                 ROOT/'V11_single_wave/run_checks.py',ROOT/'V11_single_wave/R11_CPU_RESULT.json',*HERE.glob('*_fragment.asc')]:
        artifacts[path.relative_to(ROOT).as_posix()]=build.sha(path)
    report={'scope':'actual-source CPU layout/event checks plus K-domain guard enumeration; not CANN or hardware timing',
        'sources':{p.name:build.sha(p) for p in build.OUT.glob('*.asc')},'composition':build.verify(),
        'old_452_ordinary_outputs_equal_archived_R11':True,'new_domain_outputs_checked_against_FP64':True,
        'baseline_generic_path_not_executed_for_new_domains':True,'known_numerical_limitations_remain':True,
        'negative_controls':negatives,'runs':{k:{kk:vv for kk,vv in v.items() if kk!='output_bits'} for k,v in runs.items()},
        'cann_compiled_locally':False,'npu_tested_locally':False,'artifacts':artifacts}
    for path in [HERE/'CHECKS.json',build.OUT/'CPU_CHECKS.json']:build.write(path,json.dumps(report,indent=2)+'\n')
    print('K-domain sources, old-domain regression and both injected faults checked.',flush=True)
if __name__=='__main__':main()

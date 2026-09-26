"""Exercise R11/R13/R14 device source with each actual launch/tiling plan."""
from pathlib import Path
import importlib.util,json,os,shutil,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;BUILD=HERE/'cpu_build'
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m
build=load('flex_source_build',HERE/'build.py')
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
    if version=='R11':return
    frag=(HERE/(version+'_macro_fragment.asc')).read_text(encoding='utf-8')
    assert frag in (build.OUT/(build.NAMES[version]+'.asc')).read_text(encoding='utf-8')
    extract=prior.prior.prior.prior.parent.previous.parent.extract
    s=extract(frag,'// BMMS11R2_CPU_EXTRACT_END');c=prior.build.consumer(s)
    helper='    __aicore__ inline void FinishReduction(){\n        const int worker=AscendC::GetBlockIdx();\n'+prior.build.old_finish(frag)+'    }\n'
    c=once(c,'    __aicore__ inline void Process(){',helper+'    __aicore__ inline void Process(){')
    s=once(s,prior.build.consumer(s),c);build.write(BUILD/'ring_extracted.hpp',s)
def harness(version):
    s=prior.harness('R11')
    s='#define FLEX_VARIANT '+('0' if version=='R11' else version[1:])+'\n'+s
    if version!='R11':
        s=once(s,'''        auto base=bmms11r2::MakeR10Plan(B,M,N,K,cores);
        Mock::need(base.blocks==r2.blocks&&base.mTiles==r2.mTiles&&base.nTiles==r2.nTiles,"changed launch/domain");
        if(base.pM!=r2.pM||base.pN!=r2.pN){
            Mock::need(base.tasks>base.blocks&&r2.tasks==r2.blocks&&r2.tasks==B*r2.pM*r2.pN,"invalid wave removal");
            auto a=bmms11r2::ExistingPeak(base),b=bmms11r2::SingleWavePeak(r2);
            Mock::need(8*b.tiles<=7*a.tiles&&8*b.cells<=7*a.cells&&8*b.input<=7*a.input,"new grid margin violated");
        }else Mock::need(base.tasks==r2.tasks,"task count changed without grid change");''',
        '''        auto base=bmms11r2::MakeR11Plan(B,M,N,K,cores);
        Mock::need(base.mTiles==r2.mTiles&&base.nTiles==r2.nTiles,"changed tile domain");
        Mock::need(r2.blocks==std::min(cores,r2.tasks)&&r2.tasks==B*r2.pM*r2.pN,"inconsistent launch/tasks");
        if(base.pM!=r2.pM||base.pN!=r2.pN){
            Mock::need(cores<=64&&B<=cores&&base.blocks==cores&&r2.blocks<cores&&4*r2.blocks>=3*cores,
                "invalid smaller launch");
            Mock::need(FLEX_VARIANT==13?base.tasks>cores:base.tasks==cores,"changed outside regime");
            auto a=bmms11r2::ExistingPeak(base),b=bmms11r2::SingleWavePeak(r2);
            Mock::need(8*b.tiles<=7*a.tiles&&8*b.cells<=7*a.cells&&8*b.input<=7*a.input,"flex margin violated");
        }else Mock::need(base.tasks==r2.tasks&&base.blocks==r2.blocks,"changed launch without grid change");''')
    s=once(s,'int macroRoutes=0,residualRoutes=0,smallRoutes=0,guardChecks=0;',
        'int macroRoutes=0,residualRoutes=0,smallRoutes=0,guardChecks=0,flexChanges=0;')
    s=once(s,'    OpStats::reset();','''#if FLEX_VARIANT
    if(useMacro){auto base=bmms11r2::MakeR11Plan(B,M,N,K,cores);
        if(p.pM!=base.pM||p.pN!=base.pN){
            ++flexChanges;Mock::need(p.blocks==p.tasks&&p.blocks<base.blocks,"changed source execution not using smaller launch");
        }
    }
#endif
    OpStats::reset();''')
    s=once(s,'    std::ostringstream fixtures;', '''    for(int rev=0;rev<2;++rev){
        dense<half,false,true>(1,896,768,256,8,0,rev);
        dense<bfloat16_t,true,false>(1,880,752,288,8,1,rev);
        // Non-divisible B: 21 tasks/20 groups becomes 18 tasks/18 groups.
        dense<half,false,false>(3,1024,256,256,20,0,rev);
        dense<bfloat16_t,true,true>(3,1008,256,288,20,1,rev);
        // R14-only: a one-wave layout becomes 7 balanced tasks on 7 groups.
        dense<half,true,false>(1,384,1792,256,8,0,rev);
        dense<bfloat16_t,false,true>(1,368,1776,288,8,1,rev);
    }
    std::ostringstream fixtures;''')
    s=once(s,'<<",\\\"max_abs\\\":"<<maxError',
        '<<",\\\"flex_changed_route_runs\\\":"<<flexChanges<<",\\\"max_abs\\\":"<<maxError')
    return s
def main():
    build.verify();BUILD.mkdir(exist_ok=True);compiler=shutil.which(os.environ.get('CXX','g++'));assert compiler
    grid=json.loads((HERE/'GRID_CHECKS.json').read_text(encoding='utf-8'))
    for rel,digest in grid['source_sha256'].items():assert build.sha(ROOT/rel)==digest
    args=[compiler,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-pthread','-DCHECK_R01=1','-DCHECK_R04=1','source_checks.cpp']
    runs={}
    for version in ['R11','R13','R14']:
        prepare(version);build.write(BUILD/'source_checks.cpp',harness(version));exe=BUILD/(version+'.exe')
        call(args+['-o',str(exe)],version+'_compile');data=json.loads(call([str(exe)],version+'_run').stdout);runs[version]=data
        assert data['source_runs']==464 and data['repeat_pairs']==232,(data['source_runs'],data['repeat_pairs'])
        assert data['strict_misses']==data['combined_misses']==0 and data['known_precision_limitations']==3
        assert data['reduction_checks']['checked']==22 and data['reduction_checks']['parallel_cases']==0
        if version!='R11':assert data['flex_changed_route_runs']>=4
        build.write(HERE/(version+'_CPU_RESULT.json'),json.dumps(data,indent=2)+'\n')
        print(version+': '+json.dumps({k:v for k,v in data.items() if k not in ['output_bits','reduction_checks']}),flush=True)
    assert runs['R11']['output_bits']==runs['R13']['output_bits']==runs['R14']['output_bits']
    old=json.loads((ROOT/'V11_single_wave/R11_CPU_RESULT.json').read_text(encoding='utf-8'))
    for key,bits in old['output_bits'].items():assert runs['R11']['output_bits'][key]==bits
    for key in ['peak_arena_bytes','fixtures','mixed_route_sequence','mixed_ring_bytes_per_group','mixed_ready_packets']:
        assert runs['R11'][key]==runs['R13'][key]==runs['R14'][key],key
    previous=json.loads((ROOT/'V11_single_wave/CHECKS.json').read_text(encoding='utf-8'));artifacts=dict(previous['artifacts'])
    for rel,digest in artifacts.items():assert build.sha(ROOT/rel)==digest,rel
    for path in [HERE/'build.py',Path(__file__),HERE/'flexible_plan_tail.asc',HERE/'audit_plans.py',
                 HERE/'grid_checks.cpp.in',HERE/'R13_macro_fragment.asc',HERE/'R14_macro_fragment.asc',
                 ROOT/'V11_single_wave/run_checks.py',ROOT/'V11_single_wave/R11_CPU_RESULT.json']:
        artifacts[path.relative_to(ROOT).as_posix()]=build.sha(path)
    report={'scope':'actual-source CPU storage/event execution with reduced launch plans; not hardware timing or compilation',
        'sources':{p.name:build.sha(p) for p in build.OUT.glob('*.asc')},'composition':build.verify(),
        'ordinary_outputs_equal_bitwise':True,'known_numerical_limitations_remain':True,
        'negative_controls':grid['negative_controls'],'grid_checks':grid,
        'runs':{k:{kk:vv for kk,vv in v.items() if kk!='output_bits'} for k,v in runs.items()},
        'cann_compiled_locally':False,'npu_tested_locally':False,'artifacts':artifacts}
    for path in [HERE/'CHECKS.json',build.OUT/'CPU_CHECKS.json']:build.write(path,json.dumps(report,indent=2)+'\n')
    print('Three source variants, smaller launch protocols, output comparisons and plan fault checks passed.',flush=True)
if __name__=='__main__':main()

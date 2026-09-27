"""Replay actual producer/consumer source and audit independent route experiments."""
from pathlib import Path
import importlib.util,json,shutil,subprocess,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;BUILD=HERE/'cpu_build'
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
b=load('multi_build',HERE/'build.py');prior=load('multi_prior',ROOT/'V11_native_targeted25/run_checks.py')
def redirect(m,seen=None):
    seen=set() if seen is None else seen
    if id(m) in seen:return
    seen.add(id(m))
    if hasattr(m,'BUILD'):m.BUILD=BUILD
    for name in ['old','native','previous','flex','prior','parent']:
        if hasattr(m,name):redirect(getattr(m,name),seen)
def prepare():
    redirect(prior);prior.prepare()
    expected=json.loads((ROOT/'V11_native_targeted25/CHECKS.json').read_text(encoding='utf-8'))['harness_headers']
    for name,digest in expected.items():assert b.sha(BUILD/name)==digest,(name,'inherited model mismatch')
    base=b.BASE.read_text(encoding='utf-8')
    residual=b.between(base,'namespace bmms11d {','// BMMS9_CPU_EXTRACT_END')
    b.write(BUILD/'r25_residual.hpp','#define BMMS11D_K_BLOCK 128\n'+residual)
    for n,name in b.NAMES.items():
        source=(b.OUT/(name+'.asc')).read_text(encoding='utf-8')
        frag=b.between(source,f'// BMMS{n}_BEGIN',f'// BMMS{n}_CPU_EXTRACT_END')
        b.write(BUILD/f'r{n}_extracted.hpp',frag)
    b.write(BUILD/'source_checks.cpp',(HERE/'source_checks.cpp.in').read_text(encoding='utf-8'))
def call(args,stem,error=None):
    p=subprocess.run(args,cwd=BUILD,capture_output=True,text=True,timeout=900)
    b.write(BUILD/(stem+'.stdout.txt'),p.stdout);b.write(BUILD/(stem+'.stderr.txt'),p.stderr)
    if error:
        errors=(error,) if isinstance(error,str) else error
        assert p.returncode and any(e in p.stderr for e in errors),(stem,p.returncode,p.stderr[-2000:])
    elif p.returncode:raise RuntimeError(stem+': '+p.stderr[-3000:]+p.stdout[-500:])
    return p
def main():
    b.verify();BUILD.mkdir(exist_ok=True)
    before={p.name:b.sha(p) for p in BUILD.glob('*.hpp')}
    old_harness=b.sha(BUILD/'source_checks.cpp') if (BUILD/'source_checks.cpp').exists() else ''
    prepare();compiler=shutil.which('g++');assert compiler
    if '--faults-only' in sys.argv:
        assert before=={p.name:b.sha(p) for p in BUILD.glob('*.hpp')}
        assert old_harness==b.sha(BUILD/'source_checks.cpp')
    args=[compiler,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-pthread','-DCHECK_R01=1','source_checks.cpp']
    runs={}
    for name,mode in [('R25',0),('CANDIDATES',1)]:
        exe=BUILD/(name+'.exe')
        if '--faults-only' in sys.argv:data=json.loads((HERE/(name+'_CPU_RESULT.json')).read_text(encoding='utf-8'))
        else:
            call(args+['-DCANDIDATE='+str(mode),'-o',str(exe)],name+'_compile')
            data=json.loads(call([str(exe)],name+'_run').stdout)
        runs[name]=data
        assert data['strict_misses']==0
        b.write(HERE/(name+'_CPU_RESULT.json'),json.dumps(data,indent=2)+'\n')
        print(name+': '+json.dumps({k:v for k,v in data.items() if k not in ['output_bits','fixtures']}),flush=True)
    assert runs['R25']['output_bits']==runs['CANDIDATES']['output_bits']
    faults={}
    for name,file,a,z,define,error in [
        ('R29_K_ORIGIN','r29_extracted.hpp','i*p.K*16+k0*16','i*p.K*16','NEGATIVE_29','negative R29 corruption detected'),
        ('R30_PACKET','r30_extracted.hpp','if(tileSlot+1==PACKET_TILES)AscendC::CrossCoreSetFlag<0x2,PIPE_FIX>','if(tileSlot+1==1)AscendC::CrossCoreSetFlag<0x2,PIPE_FIX>','NEGATIVE_30',('published half','published ring slot','published data','before release')),
        ('R31_L0_SLOT','r31_extracted.hpp','const int s0=0,kr0','const int s0=l0Count&1,kr0','NEGATIVE_31','local event wait has no credit')]:
        path=BUILD/file;good=path.read_text(encoding='utf-8');b.write(path,b.once(good,a,z))
        try:
            exe=BUILD/(name+'.exe');call(args+['-DCANDIDATE=1','-D'+define+'=1','-o',str(exe)],name+'_compile')
            bad=call([str(exe)],name+'_run',error);faults[name]={'rejected':True,'stderr':bad.stderr.strip()}
        finally:b.write(path,good)
        print(name+': rejected',flush=True)
    report={'scope':'actual-source CPU layout/storage/event/arithmetic model; not CANN compilation or NPU timing',
        'sources':{p.name:b.sha(p) for p in b.OUT.glob('*.asc')},'composition':b.verify(),
        'outputs_equal_R25_bitwise_in_model':True,'negative_controls':faults,
        'runs':{n:{k:v for k,v in d.items() if k!='output_bits'} for n,d in runs.items()},
        'model_headers':{p.name:b.sha(p) for p in BUILD.glob('*.hpp')},
        'artifacts':{p.name:b.sha(p) for p in HERE.iterdir() if p.suffix in ['.py','.in','.asc']},
        'CANN_compiled_locally':False,'NPU_tested_locally':False,'full_domain_precision_proven':False}
    for p in [HERE/'CHECKS.json',b.OUT/'CPU_CHECKS.json']:b.write(p,json.dumps(report,indent=2)+'\n')
    print('All three producer experiments passed source replay and fault controls.',flush=True)
if __name__=='__main__':main()

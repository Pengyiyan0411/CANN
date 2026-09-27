"""Actual host-source comparison against R25; all outside-domain records equal."""
from pathlib import Path
import importlib.util,json,re,shutil,subprocess,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;BUILD=HERE/'host_build'
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
b=load('packet_host_builder',HERE/'build.py');prior=load('targeted_host26',ROOT/'V11_native_targeted25/check_host.py')
def source():
    code=prior.source().split('Run functions[]=')[0]
    src=(b.OUT/(b.NAME+'.asc')).read_text(encoding='utf-8')
    bindings=re.findall(r'^BMMS26_KERNEL\((\w+),(\w+),(true|false),(true|false)\)$',src,re.M);assert len(bindings)==8
    for name,T,ta,tb in bindings:
        dt={'half':1,'bfloat16_t':2}[T]
        code+=f'void {name}(GM_ADDR,GM_ADDR,GM_ADDR,GM_ADDR,GM_ADDR part,bmms83::NativePlan p){{nativeRecord(NATIVE,{dt},{ta},{tb},part,p);actual.strategy=3;}}\n'
    code+='#define BMMS23_SINGLE_K_CONTROL 0\n#define BMMS25_SMALL 1\n#define BMMS25_DENSE 1\nnamespace V4 {\n'
    for ns in ['bmms11r2','bmms11d','bmms23']:
        part=src[src.index('namespace '+ns+' {\nstatic inline bool TryLaunch('):]
        code+=f'namespace {ns} {{using namespace ::{ns};\n'+b.function(part,'static inline bool TryLaunch(')+'\n}\n'
    for ns in ['bmms25','bmms26']:
        part=src[src.index('namespace '+ns+' {\nstatic inline bool TryLaunch('):]
        code+=f'namespace {ns} {{using namespace ::bmms83;\n'
        if ns=='bmms25':code+=b.function(src,'static inline int Select(')+'\n'
        code+=b.function(part,'static inline bool TryLaunch(')+'\n}\n'
    code+=b.function(src,'extern "C" void run_kernel(').replace('extern "C" void run_kernel','void run')+'\n}\n'
    code=code.replace('NAME<<<p.blocks,nullptr,stream>>>','recordBlocks(p.blocks), NAME').replace('NAME<<<p.workers,nullptr,stream>>>','recordBlocks(p.workers), NAME');assert '<<<' not in code
    tests=prior.source().split('uint64_t checks=0,unchanged=0,hits[3]={},routes[6]={};',1)[1]
    begin=tests.index('    for(int i=1;i<4;++i){');end=tests.index('\n}\nint main(){',begin)
    tests=tests[:begin]+'''    Record expected=baseline;
    const bool target=baseline.route==NATIVE&&B==1&&K==128&&M>32&&N>32&&baseline.blocks>1;
    if(target)expected.strategy=3;
    Record got=execute(1,B,M,N,K,dt,ta,tb,cores);
    need(got==expected,"non-target dispatch or target plan changed");++checks;
    ++hits[target?2:baseline.strategy==1?1:0];if(!target)++unchanged;
'''+tests[end:]
    return code+'Run functions[]={V1::run,V4::run};\nuint64_t checks=0,unchanged=0,hits[3]={},routes[6]={};'+tests
def main():
    b.verify();BUILD.mkdir(exist_ok=True);code=source();cpp=BUILD/'host.cpp';exe=BUILD/'host.exe';b.write(cpp,code)
    args=[shutil.which('g++'),'-std=c++20','-O2',str(cpp),'-o',str(exe)]
    subprocess.run(args,check=True);p=subprocess.run([str(exe)],capture_output=True,text=True,timeout=300)
    if p.returncode:raise RuntimeError(p.stderr)
    result=json.loads(p.stdout)
    bad=b.once(code,'if(!('+b.DENSE+'))return false;','if(!(p.K==128&&p.M>32&&p.N>32&&p.blocks>1))return false;')
    try:
        b.write(cpp,bad);subprocess.run(args,check=True);q=subprocess.run([str(exe)],capture_output=True,text=True,timeout=300)
        assert q.returncode and 'non-target dispatch or target plan changed' in q.stderr
    finally:b.write(cpp,code)
    result.update(scope='actual run_kernel and TryLaunch, CPU recording stubs, no CANN/NPU execution',
        all_non_target_records_equal_R25=True,Case5_metadata_records_equal_R25=True,widened_guard_fault_rejected=True,new_kernel_bindings=8,
        sources={p.name:b.sha(p) for p in b.OUT.glob('*.asc')},checker_sha256=b.sha(Path(__file__)))
    for p in [HERE/'HOST_CHECKS.json',b.OUT/'HOST_CHECKS.json']:b.write(p,json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()

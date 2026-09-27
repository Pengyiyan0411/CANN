"""Actual entry dispatch versus R25, plus independent partition/resource invariants."""
from pathlib import Path
import importlib.util,json,re,shutil,subprocess,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;BUILD=HERE/'host_build'
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
b=load('multi_host_builder',HERE/'build.py');prior=load('multi_old_host',ROOT/'V11_native_targeted25/check_host.py')
def source():
    prefix=prior.source().split('#define BMMS23_SINGLE_K_CONTROL')[0]
    for n,name in b.NAMES.items():
        code=(b.OUT/(name+'.asc')).read_text(encoding='utf-8');frag=b.fragment(n,b.BASE.read_text(encoding='utf-8'))
        prefix+=frag[:frag.index('template<class T,bool TA,bool TB') ]+'}\n'
        bindings=re.findall(r'^BMMS'+str(n)+r'_KERNEL\((\w+),(\w+),(true|false),(true|false)\)$',code,re.M);assert len(bindings)==8
        for fun,T,ta,tb in bindings:
            dt={'half':1,'bfloat16_t':2}[T];route={29:'RESIDUAL',30:'NATIVE',31:'MACRO'}[n]
            prefix+=f'void {fun}(GM_ADDR,GM_ADDR,GM_ADDR,GM_ADDR,GM_ADDR part,bmms83::NativePlan p){{nativeRecord({route},{dt},{ta},{tb},part,p);actual.strategy={n};}}\n'
    for i,file in enumerate([b.BASE]+[b.OUT/(name+'.asc') for name in b.NAMES.values()]):
        code=file.read_text(encoding='utf-8')
        prefix+=f'#define BMMS23_SINGLE_K_CONTROL 0\n#define BMMS25_SMALL 1\n#define BMMS25_DENSE 1\nnamespace V{i} {{\n'
        for ns in ['bmms11r2','bmms11d','bmms23']+([f'bmms{i+28}'] if i else []):
            prefix+=f'namespace {ns} {{using namespace ::{ns};\n'+b.host(code,ns)+'\n}\n'
        prefix+='namespace bmms25 {using namespace ::bmms83;\n'+b.function(code,'static inline int Select(')+'\n'+b.host(code,'bmms25')+'\n}\n'
        prefix+=b.function(code,'extern "C" void run_kernel(').replace('extern "C" void run_kernel','void run')+'\n}\n#undef BMMS23_SINGLE_K_CONTROL\n#undef BMMS25_SMALL\n#undef BMMS25_DENSE\n'
    prefix=prefix.replace('NAME<<<p.blocks,nullptr,stream>>>','recordBlocks(p.blocks), NAME').replace('NAME<<<p.workers,nullptr,stream>>>','recordBlocks(p.workers), NAME');assert '<<<' not in prefix
    prefix+='using Run=void(*)(GM_ADDR,const TensorGroupInfo&,GM_ADDR,const TensorGroupInfo&,GM_ADDR,const TensorGroupInfo&,int64_t,aclrtStream,bool,bool);\nRun functions[]={V0::run,V1::run,V2::run,V3::run};\n'
    return prefix+(HERE/'host_checks.cpp.in').read_text(encoding='utf-8')
def main():
    b.verify();BUILD.mkdir(exist_ok=True);code=source();cpp=BUILD/'host.cpp';b.write(cpp,code);exe=BUILD/'host.exe'
    args=[shutil.which('g++'),'-std=c++20','-O2',str(cpp),'-o',str(exe)]
    c=subprocess.run(args,capture_output=True,text=True);b.write(BUILD/'compile.stderr.txt',c.stderr)
    if c.returncode:raise RuntimeError(c.stderr[:5000])
    p=subprocess.run([str(exe)],capture_output=True,text=True,timeout=300);b.write(BUILD/'run.stderr.txt',p.stderr)
    if p.returncode:raise RuntimeError(p.stderr)
    result=json.loads(p.stdout)
    bad=b.once(code,'p.K==128&&p.B==1&&p.M>=128&&p.N>32&&p.blocks>1','p.K==128&&p.M>=128&&p.N>32&&p.blocks>1')
    try:
        b.write(cpp,bad);c=subprocess.run(args,capture_output=True,text=True);assert c.returncode==0,c.stderr
        q=subprocess.run([str(exe)],capture_output=True,text=True,timeout=300)
        assert q.returncode and 'non-target dispatch' in q.stderr,q.stderr
    finally:b.write(cpp,code)
    result.update(scope='actual run_kernel and TryLaunch with recording kernel bindings; no device timing',
        widened_Native_B_guard_fault_rejected=True,kernel_bindings=24,all_original_routes_retained=True,
        sources={p.name:b.sha(p) for p in b.OUT.glob('*.asc')},checker_sha256=b.sha(Path(__file__)))
    for p in [HERE/'HOST_CHECKS.json',b.OUT/'HOST_CHECKS.json']:b.write(p,json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()

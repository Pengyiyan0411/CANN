"""Execute all actual host dispatchers and compare non-target launch records."""
from pathlib import Path
import importlib.util,json,re,shutil,subprocess,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;BUILD=HERE/'host_build'
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
b=load('targeted_host_builder',HERE/'build.py');prior=load('d24_host_reuse',ROOT/'V11_diagnostics24/check_host.py')

def source():
    prefix=prior.host_source().split('\n#define BMMS23_SINGLE_K_CONTROL')[0]
    prefix=b.once(prefix,'int dt=0,ta=0,tb=0,blocks=0;','int dt=0,ta=0,tb=0,blocks=0,strategy=0;')
    candidate=(b.OUT/'R25_NATIVE_TARGETED.asc').read_text(encoding='utf-8')
    bindings=re.findall(r'^BMMS25_KERNEL\((\w+),(\w+),(true|false),(true|false),(true|false)\)$',candidate,re.M)
    assert len(bindings)==16
    for name,T,ta,tb,small in bindings:
        dt={'half':1,'bfloat16_t':2}[T];strategy=1 if small=='true' else 2
        prefix+=f'void {name}(GM_ADDR,GM_ADDR,GM_ADDR,GM_ADDR,GM_ADDR part,bmms83::NativePlan p){{nativeRecord(NATIVE,{dt},{ta},{tb},part,p);actual.strategy={strategy};}}\n'
    files=[('CONTROL_R23',(0,0))]+list(b.VARIANTS.items())
    for i,(name,(small,dense)) in enumerate(files):
        code=(b.OUT/(name+'.asc')).read_text(encoding='utf-8')
        prefix+=f'#define BMMS23_SINGLE_K_CONTROL 0\n#define BMMS25_SMALL {small}\n#define BMMS25_DENSE {dense}\nnamespace V{i} {{\n'
        for ns in ['bmms11r2','bmms11d','bmms23']:
            part=code[code.index('namespace '+ns+' {\nstatic inline bool TryLaunch('):]
            prefix+=f'namespace {ns} {{using namespace ::{ns};\n'+b.function(part,'static inline bool TryLaunch(')+'\n}\n'
        if i:
            part=code[code.index('namespace bmms25 {\nstatic inline bool TryLaunch('):]
            prefix+='namespace bmms25 {using namespace ::bmms83;\n'+b.function(code,'static inline int Select(')+'\n'+b.function(part,'static inline bool TryLaunch(')+'\n}\n'
        prefix+=b.function(code,'extern "C" void run_kernel(').replace('extern "C" void run_kernel','void run')+'\n}\n#undef BMMS23_SINGLE_K_CONTROL\n#undef BMMS25_SMALL\n#undef BMMS25_DENSE\n'
    prefix=prefix.replace('NAME<<<p.blocks,nullptr,stream>>>','recordBlocks(p.blocks), NAME').replace('NAME<<<p.workers,nullptr,stream>>>','recordBlocks(p.workers), NAME')
    assert '<<<' not in prefix
    prefix+='using Run=void(*)(GM_ADDR,const TensorGroupInfo&,GM_ADDR,const TensorGroupInfo&,GM_ADDR,const TensorGroupInfo&,int64_t,aclrtStream,bool,bool);\n'
    prefix+='Run functions[]={V0::run,V1::run,V2::run,V3::run};\n'
    # Source order: combined, small-only, dense-only.
    return prefix+r'''
uint64_t checks=0,unchanged=0,hits[3]={},routes[6]={};
Record execute(int i,int B,int M,int N,int K,int dt,bool ta,bool tb,int cores){
    TensorGroupInfo a{1,{{3,dt,{B,ta?K:M,ta?M:K}}}},b{1,{{3,dt,{B,tb?N:K,tb?K:N}}}},y{1,{{1,0,{B,0,0}}}};
    actual={};functions[i](nullptr,a,nullptr,b,nullptr,y,cores,nullptr,ta,tb);
    need(actual.launches==1&&actual.mallocs==actual.frees&&actual.syncs==actual.frees,"dispatch lifecycle mismatch");return actual;
}
void check(int B,int M,int N,int K,int dt,bool ta,bool tb,int cores){
    if(int64_t(B)*M*K>(1LL<<26)||int64_t(B)*N*K>(1LL<<26))return;
    Record baseline=execute(0,B,M,N,K,dt,ta,tb,cores);++routes[baseline.route];
    for(int i=1;i<4;++i){
        Record expected=baseline;int strategy=0;
        if(baseline.route==NATIVE&&K==128&&baseline.blocks>1){
            if(i!=3&&B>1&&M<=32&&N<=32)strategy=1;
            if(i!=2&&B==1&&M>32&&N>32)strategy=2;
        }
        expected.strategy=strategy;Record got=execute(i,B,M,N,K,dt,ta,tb,cores);
        need(got==expected,"non-target dispatch or target plan changed");++checks;++hits[strategy];if(!strategy)++unchanged;
        if(strategy==1)need(got.plan[4]==1&&got.plan[5]==1&&got.plan[6]==1&&got.plan[7]==1&&got.plan[8]==B,"small specialization requires complete per-batch tasks");
    }
}
int main(){try{
    for(int B:{1,2,3,20,64})for(int M:{16,32,48,64,128,272,1024,8192})for(int N:{16,32,48,128,144,528,1024,8192})
    for(int K:{32,64,128,256,4096})for(int cores:{1,3,20,64})check(B,M,N,K,1,false,false,cores);
    for(int dt:{1,2})for(bool ta:{false,true})for(bool tb:{false,true})for(int c:{1,3,20})
    for(auto s:std::vector<std::array<int,4>>{{3,16,16,128},{7,32,32,128},{1,144,272,128},{1,32,80,64},
        {1,32,48,4096},{3,144,272,288},{1,128,256,1024},{3,80,1,96},{3,1,80,96},{3,3,3,64},{1,17,19,264}})
        check(s[0],s[1],s[2],s[3],dt,ta,tb,c);
    for(int r=0;r<6;++r)need(routes[r]>0,"missing old-route coverage");
    for(int i=0;i<3;++i)need(hits[i]>0,"missing target/non-target coverage");
    std::cout<<"{\"dispatch_checks\":"<<checks<<",\"unchanged_full_launch_records\":"<<unchanged
        <<",\"small_selections\":"<<hits[1]<<",\"dense_selections\":"<<hits[2]<<",\"original_routes\":[";
    for(int i=0;i<6;++i){if(i)std::cout<<",";std::cout<<routes[i];}std::cout<<"]}\n";
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
'''

def main():
    b.verify();BUILD.mkdir(exist_ok=True);cpp=BUILD/'host.cpp';code=source();b.write(cpp,code);exe=BUILD/'host.exe'
    args=[shutil.which('g++'),'-std=c++20','-O2',str(cpp),'-o',str(exe)]
    subprocess.run(args,check=True);p=subprocess.run([str(exe)],capture_output=True,text=True,timeout=300)
    if p.returncode:raise RuntimeError(p.stderr)
    result=json.loads(p.stdout)
    # Widening the predicate by dropping B would silently affect an unrelated Native shape.
    assert code.count('BMMS25_SMALL&&'+b.SMALL)==3
    bad=code.replace('BMMS25_SMALL&&'+b.SMALL,'BMMS25_SMALL&&p.K==128&&p.M<=32&&p.N<=32',1)
    try:
        b.write(cpp,bad);subprocess.run(args,check=True);q=subprocess.run([str(exe)],capture_output=True,text=True,timeout=300)
        assert q.returncode and 'non-target dispatch or target plan changed' in q.stderr
    finally:b.write(cpp,code)
    result.update(scope='actual run_kernel, Select, TryLaunch; recording kernel stubs; no device timing',
        all_original_routes_retained=True,widened_guard_fault_rejected=True,kernel_bindings=16,
        sources={p.name:b.sha(p) for p in b.OUT.glob('*.asc')},checker_sha256=b.sha(Path(__file__)))
    for p in [HERE/'HOST_CHECKS.json',b.OUT/'HOST_CHECKS.json']:b.write(p,json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()

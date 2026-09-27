"""Run the actual R25/R28 host dispatchers with recording kernel bindings."""
from pathlib import Path
import importlib.util,json,re,shutil,subprocess,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;BUILD=HERE/'host_build'
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
b=load('compact_host_builder',HERE/'build.py')
prior=load('compact_prior_host',ROOT/'V11_native_targeted25/check_host.py')

def source():
    prefix=prior.source().split('#define BMMS23_SINGLE_K_CONTROL')[0]
    candidate=(b.OUT/(b.NAME+'.asc')).read_text(encoding='utf-8')
    part=b.fragment(b.BASE.read_text(encoding='utf-8'))
    prefix+=part[:part.index('template<class T,bool TA,bool TB>\nclass Producer')]+'}\n'
    bindings=re.findall(r'^BMMS28_KERNEL\((\w+),(\w+),(true|false),(true|false)\)$',candidate,re.M)
    assert len(bindings)==8
    for name,T,ta,tb in bindings:
        dt={'half':1,'bfloat16_t':2}[T]
        prefix+=f'void {name}(GM_ADDR,GM_ADDR,GM_ADDR,GM_ADDR,bmms23::Plan p){{splitRecord({dt},{ta},{tb},p);actual.strategy=28;}}\n'
    for i,file in enumerate([b.BASE,b.OUT/(b.NAME+'.asc')]):
        code=file.read_text(encoding='utf-8')
        prefix+=f'#define BMMS23_SINGLE_K_CONTROL 0\n#define BMMS25_SMALL 1\n#define BMMS25_DENSE 1\nnamespace V{i} {{\n'
        for ns in ['bmms11r2','bmms11d','bmms23']+(['bmms28'] if i else []):
            p=code[code.index('namespace '+ns+' {\nstatic inline bool TryLaunch('):]
            prefix+=f'namespace {ns} {{using namespace ::{ns};\n'+b.function(p,'static inline bool TryLaunch(')+'\n}\n'
        p=code[code.index('namespace bmms25 {\nstatic inline bool TryLaunch('):]
        prefix+='namespace bmms25 {using namespace ::bmms83;\n'+b.function(code,'static inline int Select(')+'\n'+b.function(p,'static inline bool TryLaunch(')+'\n}\n'
        prefix+=b.function(code,'extern "C" void run_kernel(').replace('extern "C" void run_kernel','void run')+'\n}\n#undef BMMS23_SINGLE_K_CONTROL\n#undef BMMS25_SMALL\n#undef BMMS25_DENSE\n'
    prefix=prefix.replace('NAME<<<p.blocks,nullptr,stream>>>','recordBlocks(p.blocks), NAME').replace('NAME<<<p.workers,nullptr,stream>>>','recordBlocks(p.workers), NAME')
    assert '<<<' not in prefix
    prefix+='using Run=void(*)(GM_ADDR,const TensorGroupInfo&,GM_ADDR,const TensorGroupInfo&,GM_ADDR,const TensorGroupInfo&,int64_t,aclrtStream,bool,bool);\nRun functions[]={V0::run,V1::run};\n'
    return prefix+r'''
uint64_t checks=0,unchanged=0,hits=0,case5=0,routes[6]={},maxUB=0,maxStripes=0;
Record execute(int i,int B,int M,int N,int K,int dt,bool ta,bool tb,int cores){
    TensorGroupInfo a{1,{{3,dt,{B,ta?K:M,ta?M:K}}}},b{1,{{3,dt,{B,tb?N:K,tb?K:N}}}},y{1,{{1,0,{B,0,0}}}};
    actual={};functions[i](nullptr,a,nullptr,b,nullptr,y,cores,nullptr,ta,tb);
    need(actual.launches==1&&actual.mallocs==actual.frees&&actual.syncs==actual.frees,"dispatch lifecycle mismatch");return actual;
}
void check(int B,int M,int N,int K,int dt,bool ta,bool tb,int cores){
    if(int64_t(B)*M*K>(1LL<<26)||int64_t(B)*N*K>(1LL<<26))return;
    Record baseline=execute(0,B,M,N,K,dt,ta,tb,cores);++routes[baseline.route];
    bool hit=B==1&&M>=16&&M<=64&&N>=16&&N<=128&&M%16==0&&N%16==0&&M*N<=4096
        &&K>=4096&&K<=8192&&K%32==0&&cores>=8&&cores<=64;
    Record expected=baseline;if(hit)expected.strategy=28;
    Record got=execute(1,B,M,N,K,dt,ta,tb,cores);
    need(got==expected,"non-target dispatch or target plan changed");++checks;
    if(hit){
        ++hits;int S=K==8192&&cores>=16?16:8;
        need(got.route==SPLIT&&got.plan[6]==S&&got.blocks==S&&got.allocation==uint64_t(S)*32768,"compact plan differs from original K split");
        int stripe=std::min(M,(32768/S/N/16)*16),stripes=(M+stripe-1)/stripe;
        need(stripe>=16&&stripe%16==0,"invalid stripe geometry");
        uint64_t ub=uint64_t(S)*stripe*N*4+stripe*4+M*8+32;
        need(ub<=192*1024,"compact UB budget exceeded");maxUB=std::max(maxUB,ub);maxStripes=std::max(maxStripes,uint64_t(stripes));
        for(int r=0;r<M;r+=stripe){int mr=std::min(stripe,M-r),cells=mr*N;
            need((r*N*4)%32==0&&(cells*4)%32==0&&(32768-cells*4)>=0,"unaligned/negative DMA parameter");
            need(uint64_t(r*N)+(S-1)*8192+cells<=uint64_t(S)*8192,"compact DMA exceeds workspace");
        }
    }else ++unchanged;
    if(B>1&&M<=32&&N<=32&&K==128){need(got==baseline,"R25 Case5 protection failed");++case5;}
}
int main(){try{
    for(int B:{1,2,3,20,64})for(int M:{16,32,48,64,80,128,272,1024})for(int N:{16,32,64,80,128,144,256,1024})
    for(int K:{32,64,128,256,480,4064,4096,4104,8192})for(int c:{0,1,7,8,15,16,20,64,65})check(B,M,N,K,1,false,false,c);
    for(int M=16;M<=64;M+=16)for(int N=16;N<=128;N+=16)for(int K=4096;K<=8192;K+=32)
    for(int c:{7,8,15,16,20,64})for(int dt:{1,2})for(bool ta:{false,true})for(bool tb:{false,true})check(1,M,N,K,dt,ta,tb,c);
    for(int dt:{1,2})for(bool ta:{false,true})for(bool tb:{false,true})for(int c:{1,7,8,20,64})
    for(auto s:std::vector<std::array<int,4>>{{2,16,16,128},{7,32,32,128},{1,144,272,128},{1,48,48,128},
        {1,48,96,4096},{3,144,272,288},{1,128,256,1024},{3,80,1,96},{3,1,80,96},{3,3,3,64},{1,17,19,264}})
        check(s[0],s[1],s[2],s[3],dt,ta,tb,c);
    for(int r=0;r<6;++r)need(routes[r]>0,"missing old route");
    need(hits&&unchanged&&case5&&maxStripes==3,"missing boundary coverage");
    std::cout<<"{\"dispatch_checks\":"<<checks<<",\"unchanged_full_launch_records\":"<<unchanged<<",\"compact_selections\":"<<hits
        <<",\"Case5_metadata_protection_checks\":"<<case5<<",\"max_UB_bytes\":"<<maxUB<<",\"max_stripes\":"<<maxStripes<<",\"original_routes\":[";
    for(int r=0;r<6;++r){if(r)std::cout<<",";std::cout<<routes[r];}std::cout<<"]}\n";
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
'''

def main():
    b.verify();BUILD.mkdir(exist_ok=True);code=source();cpp=BUILD/'host.cpp';b.write(cpp,code);exe=BUILD/'host.exe'
    args=[shutil.which('g++'),'-std=c++20','-O2',str(cpp),'-o',str(exe)]
    subprocess.run(args,check=True);p=subprocess.run([str(exe)],capture_output=True,text=True,timeout=300)
    if p.returncode:raise RuntimeError(p.stderr)
    result=json.loads(p.stdout)
    bad=b.once(code,'if(B!=1||M>64||N>128||int64_t(M)*N>4096)','if(M>64||N>128||int64_t(M)*N>4096)')
    try:
        b.write(cpp,bad);subprocess.run(args,check=True);p=subprocess.run([str(exe)],capture_output=True,text=True,timeout=300)
        assert p.returncode and 'non-target dispatch or target plan changed' in p.stderr,p.stderr
    finally:b.write(cpp,code)
    result.update(scope='actual run_kernel, Eligible, MakePlan and TryLaunch; recording device bindings; no NPU timing',
        widened_B_guard_fault_rejected=True,kernel_bindings=8,all_original_routes_retained=True,
        sources={p.name:b.sha(p) for p in b.OUT.glob('*.asc')},checker_sha256=b.sha(Path(__file__)))
    for p in [HERE/'HOST_CHECKS.json',b.OUT/'HOST_CHECKS.json']:b.write(p,json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()

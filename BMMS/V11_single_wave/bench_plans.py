"""Local CPU cost of actual R10/R11 host planners; not device timing."""
from pathlib import Path
import hashlib,json,platform,shutil,subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;BUILD=HERE/'cpu_build'
def main():
    BUILD.mkdir(exist_ok=True)
    template=(ROOT/'V11_grid_packets/grid_checks.cpp.in').read_text(encoding='utf-8')
    source=template[:template.index('// INSERT_PLANS')];paths={
        'baseline':ROOT/'V11_recovery/one_wave_macro_fragment.asc','candidate':HERE/'expanded_macro_fragment.asc'}
    for ns,path in paths.items():
        s=path.read_text(encoding='utf-8');body=s[s.index('namespace bmms11r2 {'):s.index('static inline uint64_t RingBytes(')]
        source+=body.replace('namespace bmms11r2 {','namespace '+ns+' {',1)+'}\n'
    source+=r'''
#include <chrono>
#include <iomanip>
volatile uint64_t sink=0;
__attribute__((noinline)) bmms83::NativePlan oldplan(int b,int m,int n,int k,int c){return baseline::MakePlan(b,m,n,k,c);}
__attribute__((noinline)) bmms83::NativePlan newplan(int b,int m,int n,int k,int c){return candidate::MakePlan(b,m,n,k,c);}
double measure(bmms83::NativePlan(*f)(int,int,int,int,int),const std::array<int,5>&d){
    auto start=std::chrono::steady_clock::now();
    for(int i=0;i<1000;++i){auto p=f(d[0],d[1],d[2],d[3],d[4]);sink=sink+p.tasks+p.pM+p.pN;}
    return std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-start).count()/1000;
}
int main(){bool first=true;std::cout<<std::setprecision(10)<<"[";
    for(auto d:std::vector<std::array<int,5>>{{1,512,768,256,6},{1,1024,1024,256,20},
        {1,384,768,256,5},{1,4096,4096,256,20},{8,4096,4096,256,20},
        {3,896,2048,256,60},{1,8064,8192,256,64},{1,8192,8192,256,64}}){
        auto a=oldplan(d[0],d[1],d[2],d[3],d[4]),b=newplan(d[0],d[1],d[2],d[3],d[4]);
        std::vector<double>x,y;for(int r=0;r<5;++r){x.push_back(measure(oldplan,d));y.push_back(measure(newplan,d));}
        std::sort(x.begin(),x.end());std::sort(y.begin(),y.end());if(!first)std::cout<<",";first=false;
        std::cout<<"{\"shape\":["<<d[0]<<","<<d[1]<<","<<d[2]<<","<<d[3]<<"],\"cores\":"<<d[4]
            <<",\"R10_grid\":["<<a.pM<<","<<a.pN<<"],\"R11_grid\":["<<b.pM<<","<<b.pN
            <<"],\"R10_tasks\":"<<a.tasks<<",\"R11_tasks\":"<<b.tasks
            <<",\"R10_host_median_us\":"<<x[2]<<",\"R11_host_median_us\":"<<y[2]<<"}";
    }std::cout<<"]\n";
}
'''
    cpp=BUILD/'host_bench.cpp';cpp.write_text(source,encoding='utf-8',newline='\n')
    compiler=shutil.which('g++');assert compiler;exe=BUILD/'host_bench.exe'
    subprocess.run([compiler,'-std=c++20','-O2',str(cpp),'-o',str(exe)],check=True)
    runs=json.loads(subprocess.check_output([str(exe)],text=True))
    report={'scope':'local Windows CPU host microbenchmark, not NPU duration or TLE certification',
            'environment':platform.platform(),'compiler':subprocess.check_output([compiler,'--version'],text=True).splitlines()[0],
            'samples':5,'calls_per_sample':1000,'source_sha256':{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths.values()},'runs':runs}
    (HERE/'HOST_BENCH.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()

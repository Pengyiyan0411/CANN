"""Measure bounded host-planner cost on this CPU; never treat it as NPU latency."""
from pathlib import Path
import importlib.util,json,platform,shutil,subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;BUILD=HERE/'cpu_build'
spec=importlib.util.spec_from_file_location('flex_audit',HERE/'audit_plans.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
def main():
    BUILD.mkdir(exist_ok=True);source=audit.source().split('int main(){try{',1)[0]
    source+=r'''
#include <chrono>
#include <iomanip>
volatile uint64_t sink=0;
__attribute__((noinline)) bmms83::NativePlan basePlan(int b,int m,int n,int k,int c){return baseline::MakePlan(b,m,n,k,c);}
__attribute__((noinline)) bmms83::NativePlan plan13(int b,int m,int n,int k,int c){return r13::MakePlan(b,m,n,k,c);}
__attribute__((noinline)) bmms83::NativePlan plan14(int b,int m,int n,int k,int c){return r14::MakePlan(b,m,n,k,c);}
double measure(Maker f,const std::array<int,5>&d){
    auto start=std::chrono::steady_clock::now();
    for(int i=0;i<1000;++i){auto p=f(d[0],d[1],d[2],d[3],d[4]);sink=sink+p.tasks+p.pM+p.pN+p.blocks;}
    return std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-start).count()/1000;
}
int main(){bool first=true;std::cout<<std::setprecision(10)<<"[";
    for(auto d:std::vector<std::array<int,5>>{{1,896,768,256,8},{1,880,752,288,8},
        {3,1024,256,256,20},{3,1008,256,288,20},{1,384,1792,256,8},{1,368,1776,288,8},
        {8,4096,4096,256,20},{1,4096,4096,256,20},{1,1024,1024,256,20},
        {1,8064,8192,256,64},{1,8192,8192,256,64}}){
        if(!first)std::cout<<",";first=false;
        std::cout<<"{\"shape\":["<<d[0]<<","<<d[1]<<","<<d[2]<<","<<d[3]<<"],\"cores\":"<<d[4]<<",\"plans\":{";
        Maker funcs[3]={basePlan,plan13,plan14};const char*names[3]={"R11","R13","R14"};
        for(int v=0;v<3;++v){
            auto p=funcs[v](d[0],d[1],d[2],d[3],d[4]);std::vector<double>x;
            for(int r=0;r<5;++r)x.push_back(measure(funcs[v],d));std::sort(x.begin(),x.end());
            if(v)std::cout<<",";
            std::cout<<"\""<<names[v]<<"\":{\"pM\":"<<p.pM<<",\"pN\":"<<p.pN<<",\"tasks\":"<<p.tasks
                <<",\"blocks\":"<<p.blocks<<",\"host_median_us\":"<<x[2]<<"}";
        }std::cout<<"}}";
    }std::cout<<"]\n";
}
'''
    cpp=BUILD/'host_bench.cpp';exe=BUILD/'host_bench.exe';audit.build.write(cpp,source)
    compiler=shutil.which('g++');assert compiler
    subprocess.run([compiler,'-std=c++20','-O2',str(cpp),'-o',str(exe)],check=True)
    runs=json.loads(subprocess.check_output([str(exe)],text=True))
    paths=[audit.build.OLD_FRAGMENT,HERE/'R13_macro_fragment.asc',HERE/'R14_macro_fragment.asc']
    report={'scope':'local CPU host cost; not NPU timing or TLE certification','environment':platform.platform(),
        'compiler':subprocess.check_output([compiler,'--version'],text=True).splitlines()[0],
        'samples':5,'calls_per_sample':1000,'source_sha256':{p.relative_to(ROOT).as_posix():audit.build.sha(p) for p in paths},'runs':runs}
    audit.build.write(HERE/'HOST_BENCH.json',json.dumps(report,indent=2)+'\n')
    print(json.dumps({'shapes':len(runs),'max_median_host_us':{v:max(x['plans'][v]['host_median_us'] for x in runs) for v in ['R11','R13','R14']}},indent=2))
if __name__=='__main__':main()

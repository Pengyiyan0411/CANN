"""Measure the exact R07 host planner locally; this is not a platform TLE diagnosis."""
from pathlib import Path
import hashlib
import json
import platform
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BUILD = HERE / 'cpu_build'


def main():
    BUILD.mkdir(exist_ok=True)
    paths = {'R04': ROOT / 'V11_followup/macro_ring_fragment.asc',
             'R07': ROOT / 'V11_grid_packets/r07_macro_fragment.asc',
             'R10': HERE / 'one_wave_macro_fragment.asc'}
    template = (ROOT / 'V11_grid_packets/grid_checks.cpp.in').read_text(encoding='utf-8')
    head = template[:template.index('// INSERT_PLANS')]
    parts = []
    for name, path in paths.items():
        text = path.read_text(encoding='utf-8')
        body = text[text.index('namespace bmms11r2 {'):text.index('static inline uint64_t RingBytes(')]
        parts.append(body.replace('namespace bmms11r2 {', 'namespace ' + name + ' {', 1) + '}\n')
    source = head + '\n'.join(parts) + r'''
#include <chrono>
#include <iomanip>
volatile uint64_t sink=0;
using Fn=bmms83::NativePlan(*)(int,int,int,int,int);
__attribute__((noinline)) bmms83::NativePlan oldplan(int b,int m,int n,int k,int c){return R04::MakePlan(b,m,n,k,c);}
__attribute__((noinline)) bmms83::NativePlan newplan(int b,int m,int n,int k,int c){return R07::MakePlan(b,m,n,k,c);}
__attribute__((noinline)) bmms83::NativePlan cheapplan(int b,int m,int n,int k,int c){return R10::MakePlan(b,m,n,k,c);}
double measure(Fn f,const std::array<int,5>& d){
    auto start=std::chrono::steady_clock::now();
    for(int i=0;i<100;++i){auto p=f(d[0],d[1],d[2],d[3],d[4]);sink=sink+p.pM+p.pN+p.tasks;}
    return std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-start).count()/100;
}
int main(){
    std::cout<<std::setprecision(10)<<"[";bool first=true;
    for(auto d:std::vector<std::array<int,5>>{
        {1,384,768,256,5},{1,1024,1024,256,20},{1,4096,4096,256,20},
        {8,4096,4096,256,20},{24,1024,1024,256,20},{3,144,528,256,4},
        {1,8192,8192,256,20},{1,8192,8192,256,32},{1,8192,8192,256,64},
        {64,4096,4096,256,64},{1,128,256,256,1}}){
        auto a=oldplan(d[0],d[1],d[2],d[3],d[4]),b=newplan(d[0],d[1],d[2],d[3],d[4]);
        int candidates=0,taskVisits=a.tasks;
        for(int pm=1;pm<=std::min(a.mTiles,d[4]);++pm)
        for(int pn=1;pn<=std::min(a.nTiles,d[4]);++pn){
            int tasks=d[0]*pm*pn;if(tasks>std::max(d[0],4*d[4]))break;
            if(tasks<d[4])continue;++candidates;taskVisits+=tasks;
        }
        auto cp=cheapplan(d[0],d[1],d[2],d[3],d[4]);
        std::vector<double> x,y,z;
        for(int j=0;j<5;++j){x.push_back(measure(oldplan,d));y.push_back(measure(newplan,d));z.push_back(measure(cheapplan,d));}
        std::sort(x.begin(),x.end());std::sort(y.begin(),y.end());std::sort(z.begin(),z.end());
        if(!first)std::cout<<",";first=false;
        std::cout<<"{\"shape\":["<<d[0]<<","<<d[1]<<","<<d[2]<<","<<d[3]
            <<"],\"cores\":"<<d[4]<<",\"R04_grid\":["<<a.pM<<","<<a.pN
            <<"],\"R07_grid\":["<<b.pM<<","<<b.pN<<"],\"R07_candidates\":"<<candidates
            <<",\"R07_task_visits\":"<<taskVisits<<",\"R04_median_host_us\":"<<x[2]
            <<",\"R07_median_host_us\":"<<y[2]<<",\"R07_min_host_us\":"<<y[0]
            <<",\"R07_max_host_us\":"<<y[4]<<",\"R10_grid\":["<<cp.pM<<","<<cp.pN
            <<"],\"R10_median_host_us\":"<<z[2]<<",\"R10_min_host_us\":"<<z[0]
            <<",\"R10_max_host_us\":"<<z[4]<<"}";
    }
    std::cout<<"]\n";
}
'''
    (BUILD / 'planner_bench.cpp').write_text(source, encoding='utf-8', newline='\n')
    compiler = shutil.which('g++')
    assert compiler
    runs = {}
    for opt in ['-O2', '-O0']:
        exe = BUILD / ('planner_' + opt[1:] + '.exe')
        subprocess.run([compiler, '-std=c++20', opt, str(BUILD / 'planner_bench.cpp'), '-o', str(exe)], check=True)
        result = subprocess.run([str(exe)], capture_output=True, text=True, check=True, timeout=120)
        runs[opt] = json.loads(result.stdout)
    report = {'scope': 'local Windows CPU exact host MakePlan microbenchmark; neither NPU time nor TLE root cause',
              'environment': platform.platform(), 'compiler': subprocess.check_output([compiler, '--version'], text=True).splitlines()[0],
              'samples_per_shape': 5, 'calls_per_sample': 100,
              'fragment_sha256': {k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in paths.items()},
              'R07_platform_failure_case': 5, 'R07_platform_failure_stage': 'runtime',
              'platform_TLE_root_cause_confirmed': False, 'runs': runs}
    (HERE / 'R07_HOST_DIAGNOSIS.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

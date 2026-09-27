"""Execute actual top dispatcher and modified TryLaunch bodies with kernel recorders."""
from pathlib import Path
import importlib.util,json,shutil,subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;BUILD=HERE/'host_build'
spec=importlib.util.spec_from_file_location('builder',HERE/'build.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

def host_source():
    base=b.BASE.read_text(encoding='utf-8');f=b.function;between=b.between
    prefix=r'''#include <cstdint>
#include <cstdlib>
#include <array>
#include <vector>
#include <string>
#include <iostream>
#include <stdexcept>
#include <algorithm>
#define __aicore__
#define BMMS83_ENABLE_TREE 1
#define BMMS83_ENABLE_NATIVE 1
#define BMMS11D_K_BLOCK 128
using GM_ADDR=uint8_t*;using aclrtStream=void*;
constexpr int ACL_SUCCESS=0,ACL_MEM_MALLOC_HUGE_FIRST=0;
struct TensorInfo {int numDims;int dtype;int64_t shape[3];};
struct TensorGroupInfo {int numTensors;TensorInfo tensors[1];};
enum Route{MACRO,RESIDUAL,NATIVE,SPLIT,TREE,FALLBACK};
struct Record {
    Route route=FALLBACK;int dt=0,ta=0,tb=0,blocks=0;std::array<int,10> plan{};
    uint64_t allocation=0,partial=0;int mallocs=0,frees=0,syncs=0,launches=0;
    bool operator==(const Record&)const=default;
};
Record actual;uintptr_t allocatedBase;
void need(bool p,const char* s){if(!p)throw std::runtime_error(s);}
int aclrtMalloc(void** p,uint64_t bytes,int){*p=std::malloc(bytes);allocatedBase=(uintptr_t)*p;actual.allocation=bytes;++actual.mallocs;return *p?0:1;}
int aclrtFree(void* p){std::free(p);++actual.frees;return 0;}
int aclrtSynchronizeStream(void*){++actual.syncs;return 0;}
void recordBlocks(int n){actual.blocks=n;}
'''
    prefix+='namespace bmmmaxsum_v43 {\n'+f(base,'static inline bool UseTiny(int32_t M, int32_t N, int32_t K)')+'\n}\n'
    prefix+='namespace bmms71 {\n'+f(base,'static inline bool UseResident(')+'\n}\n'
    prefix+='namespace bmms8 {\n'+between(base,'enum class Family : int32_t {\n    Dot=0,','static inline int32_t MinH(')+f(base,'static inline bool IsFixedSmallK(')+'\n'+f(base,'static inline Family Classify(')+'\n}\n'
    prefix+=between(base,'namespace bmms83 {','constexpr int32_t PACKET_TILES=4;')+'constexpr int32_t PACKET_TILES=4;\n'
    for name in ['NativeRingBytes','NativePartialBytes']:
        prefix+=f(base,'static inline uint64_t '+name+'(')+'\n'
    prefix+=between(base,'struct TreePlan {','template<bool SUM_ROWS>static inline uint64_t TreePartialBytes(')
    prefix+=f(base,'template<bool SUM_ROWS>static inline uint64_t TreePartialBytes(')+'\n}\n'
    for ns,mark in [('bmms11r2','template<class T,bool TA,bool TB>\nclass ReuseProducer'),('bmms11d','template<class T,bool TA,bool TB>\nclass StagedProducer'),('bmms23','template<class T,bool TA,bool TB>\nclass Producer')]:
        part=base[base.index('namespace '+ns+' {'):]
        prefix+=part[:part.index(mark)]+'}\n'
    prefix+=r'''
void nativeRecord(Route r,int dt,bool ta,bool tb,GM_ADDR part,const bmms83::NativePlan& p){
    actual.route=r;actual.dt=dt;actual.ta=ta;actual.tb=tb;++actual.launches;
    actual.plan={p.B,p.M,p.N,p.K,p.mTiles,p.nTiles,p.pM,p.pN,p.tasks,p.blocks};
    actual.partial=(uintptr_t)part-allocatedBase;
}
void splitRecord(int dt,bool ta,bool tb,const bmms23::Plan& p){
    actual.route=SPLIT;actual.dt=dt;actual.ta=ta;actual.tb=tb;++actual.launches;
    actual.plan={p.B,p.M,p.N,p.K,p.mTiles,p.nTiles,p.splits,0,0,p.blocks};
}
void treeRecord(int dt,bool sum,const bmms83::TreePlan& p){
    actual.route=TREE;actual.dt=dt;actual.ta=sum;++actual.launches;
    actual.plan={p.B,p.L,p.K,p.chunks,p.padded,p.workers,p.direct,0,0,0};
}
void bmms80d_dispatch(GM_ADDR,const TensorGroupInfo&,GM_ADDR,const TensorGroupInfo&,GM_ADDR,const TensorGroupInfo&,int64_t cores,aclrtStream,bool,bool){
    actual.route=FALLBACK;actual.plan[0]=cores;++actual.launches;
}
'''
    for dt,dtype in [(1,'f16'),(2,'b16')]:
        for layout,ta,tb in [('nn',0,0),('nt',0,1),('tn',1,0),('tt',1,1)]:
            for ns,route in [('bmms11r2','MACRO'),('bmms11d','RESIDUAL')]:
                prefix+=f'void {ns}_{dtype}_{layout}(GM_ADDR,GM_ADDR,GM_ADDR,GM_ADDR,GM_ADDR part,bmms83::NativePlan p){{nativeRecord({route},{dt},{ta},{tb},part,p);}}\n'
            for K in [32,64,128]:
                prefix+=f'void bmms83_native_{dtype}_{layout}_k{K}(GM_ADDR,GM_ADDR,GM_ADDR,GM_ADDR,GM_ADDR part,bmms83::NativePlan p){{need(p.K=={K},"wrong fixed K binding");nativeRecord(NATIVE,{dt},{ta},{tb},part,p);}}\n'
            prefix+=f'void bmms23_{dtype}_{layout}(GM_ADDR,GM_ADDR,GM_ADDR,GM_ADDR,bmms23::Plan p){{splitRecord({dt},{ta},{tb},p);}}\n'
        for mode,summ in [('sum',1),('max',0)]:
            prefix+=f'void bmms83_tree_{mode}_{dtype}(GM_ADDR,GM_ADDR,GM_ADDR,GM_ADDR,bmms83::TreePlan p){{treeRecord({dt},{summ},p);}}\n'
    files=[('CONTROL_R23',None,'false')]+[(x[0],x[1],x[2]) for x in b.SPECS]+[('L00_K1_CONTROL','split','true')]
    for i,(name,route,pred) in enumerate(files):
        s=(b.OUT/(name+'.asc')).read_text(encoding='utf-8')
        prefix+=f'\n#define BMMS23_SINGLE_K_CONTROL {int(name=="L00_K1_CONTROL")}\nnamespace D{i} {{\n'
        for ns in ['bmms11r2','bmms11d','bmms23']:
            part=s[s.index('namespace '+ns+' {\nstatic inline bool TryLaunch('):]
            prefix+=f'namespace {ns} {{using namespace ::{ns};\n'+f(part,'static inline bool TryLaunch(')+'\n}\n'
        run=f(s,'extern "C" void run_kernel(').replace('extern "C" void run_kernel','void run')
        prefix+=run+'\n}\n#undef BMMS23_SINGLE_K_CONTROL\n'
    prefix=prefix.replace('NAME<<<p.blocks,nullptr,stream>>>','recordBlocks(p.blocks), NAME')
    prefix=prefix.replace('NAME<<<p.workers,nullptr,stream>>>','recordBlocks(p.workers), NAME')
    assert '<<<' not in prefix
    prefix+='using Run=void(*)(GM_ADDR,const TensorGroupInfo&,GM_ADDR,const TensorGroupInfo&,GM_ADDR,const TensorGroupInfo&,int64_t,aclrtStream,bool,bool);\n'
    prefix+='Run functions[]={'+','.join(f'D{i}::run' for i in range(len(files)))+'};\n'
    prefix+='const char* names[]={'+','.join(json.dumps(n) for n,_,_ in files)+'};\n'
    prefix+='bool predicate(int index,int B,int M,int N,int K,int cores){auto p=bmms23::MakePlan(B,M,N,K,cores);switch(index){\n'
    for i,(_,_,pred) in enumerate(files):prefix+=f'case {i}:return {pred};\n'
    prefix+='}return false;}\n'
    prefix+='int targets[]={'+','.join('-1' if r is None else {'macro':'MACRO','residual':'RESIDUAL','native':'NATIVE','split':'SPLIT','tree':'TREE','fallback':'FALLBACK'}[r] for _,r,_ in files)+'};\n'
    return prefix+r'''
uint64_t checks=0,hits=0,unaffected=0,changed=0,spaceOneProofs=0;
int routeVisits[6]={};std::vector<int> probeHits(std::size(functions)),probeMisses(std::size(functions));
Record execute(int index,int B,int M,int N,int K,int dt,bool ta,bool tb,int cores){
    TensorGroupInfo a{1,{{3,dt,{B,ta?K:M,ta?M:K}}}},b{1,{{3,dt,{B,tb?N:K,tb?K:N}}}},y{1,{{1,0,{B,0,0}}}};
    actual={};functions[index](nullptr,a,nullptr,b,nullptr,y,cores,nullptr,ta,tb);
    need(actual.launches==1,"not exactly one final dispatch");
    need(actual.mallocs==actual.frees&&actual.syncs==actual.frees,"allocation lifecycle mismatch");
    return actual;
}
void check(int B,int M,int N,int K,int dt,bool ta,bool tb,int cores){
    if(int64_t(B)*M*K>(1LL<<26)||int64_t(B)*N*K>(1LL<<26))return;
    Record baseline=execute(0,B,M,N,K,dt,ta,tb,cores);++routeVisits[baseline.route];
    for(int index=1;index<int(std::size(functions));++index){
        bool hit=targets[index]==baseline.route&&predicate(index,B,M,N,K,cores);
        Record expected=baseline;
        if(hit){++hits;++probeHits[index];
            if(baseline.route==NATIVE||baseline.route==RESIDUAL||baseline.route==MACRO){
                expected.blocks=1;expected.plan[6]=1;expected.plan[7]=1;expected.plan[8]=B;expected.plan[9]=1;
                expected.partial=baseline.route==RESIDUAL?65536:262144;
                expected.allocation=expected.partial+uint64_t(B)*M*4;
            }else if(baseline.route==SPLIT){
                int spatial=B*((M+63)/64)*((N+127)/128);
                expected.plan[6]=1;expected.plan[9]=spatial;expected.blocks=spatial;expected.allocation=uint64_t(spatial)*32768;
            }else if(baseline.route==TREE){expected.blocks=1;expected.plan[5]=1;}
            else expected.plan[0]=1;
        }else{++unaffected;++probeMisses[index];}
        Record got=execute(index,B,M,N,K,dt,ta,tb,cores);
        if(!(got==expected))throw std::runtime_error(std::string(names[index])+": unexpected plan/workspace/route change");
        if(!(got==baseline))++changed;
        if(got.route==NATIVE||got.route==RESIDUAL||got.route==MACRO){
            need(got.plan[8]==B*got.plan[6]*got.plan[7]&&got.blocks==got.plan[9],"plan task conservation failure");
        }
        ++checks;
    }
}
int main(){try{
    for(int B:{1,3,20})for(int M:{16,32,64,112,128,272})for(int N:{16,32,128,240,256,528})
    for(int K:{32,64,128,256,480,512,992,1024,4096,4128,8192})for(int cores:{2,8,20}){
        // Host-only cases: no tensor allocation or arithmetic.
        check(B,M,N,K,1,false,false,cores);
    }
    for(int dt:{1,2})for(bool ta:{false,true})for(bool tb:{false,true})for(int B:{1,3})
    for(auto s:std::vector<std::array<int,3>>{{48,32,32},{32,80,64},{144,272,128},{112,144,288},{128,256,256},
        {32,48,4096},{112,240,8192},{1,80,96},{80,1,96},{1,1,32},{3,3,64},{17,19,264}})
        check(B,s[0],s[1],s[2],dt,ta,tb,20);
    for(int c:{2,8,20,64})for(int B:{1,2,3,8})for(int M=16;M<128;M+=16)for(int N=16;N<256;N+=16){
        if(!bmms23::Eligible(B,M,N,4096,1,c))continue;
        auto p=bmms23::MakePlan(B,M,N,4096,c);
        need((B*p.mTiles*p.nTiles==1)==(B==1&&M<=64&&N<=128),"spatial-one joint implication failed");
        auto old=bmms11d::MakePlan(B,M,N,4096,c);
        need(old.tasks==B*p.mTiles*p.nTiles,"R03 tasks differ from full spatial grid inside split domain");++spaceOneProofs;
    }
    for(int i=0;i<6;++i)need(routeVisits[i]>0,"missing route coverage");
    for(size_t i=1;i<std::size(functions);++i)need(probeHits[i]>0&&probeMisses[i]>0,"probe lacks hit/miss coverage");
    std::cout<<"{\"host_dispatch_checks\":"<<checks<<",\"predicate_hit_checks\":"<<hits
        <<",\"unaffected_checks\":"<<unaffected<<",\"plan_changes\":"<<changed
        <<",\"spatial_one_implication_checks\":"<<spaceOneProofs<<",\"route_fixture_counts\":[";
    for(int i=0;i<6;++i){if(i)std::cout<<",";std::cout<<routeVisits[i];}
    std::cout<<"],\"probes\":"<<std::size(functions)-1<<"}\n";
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
'''

def main():
    b.verify();BUILD.mkdir(exist_ok=True);compiler=shutil.which('g++');assert compiler
    code=host_source();cpp=BUILD/'host.cpp';b.write(cpp,code);exe=BUILD/'host.exe'
    subprocess.run([compiler,'-std=c++20','-O2',str(cpp),'-o',str(exe)],check=True)
    result=subprocess.run([str(exe)],capture_output=True,text=True,check=True,timeout=300)
    report=json.loads(result.stdout)
    # Simulate the dangerous partial-plan edit: batch task count is stale.
    bad=code.replace(b.ONE_GROUP,'p.pM=1;p.pN=1;p.blocks=1;',1);assert bad!=code;b.write(cpp,bad)
    try:
        faultExe=BUILD/'stale_tasks.exe'
        subprocess.run([compiler,'-std=c++20','-O2',str(cpp),'-o',str(faultExe)],check=True)
        fault=subprocess.run([str(faultExe)],capture_output=True,text=True)
        assert fault.returncode and 'unexpected plan/workspace/route change' in fault.stderr
    finally:b.write(cpp,code)
    report.update(scope='actual run_kernel and TryLaunch source with kernel recording stubs; no CANN or device execution',
        stale_task_count_fault_rejected=True,all_unchanged_routes_compared_to_R23=True,
        source_sha256={p.relative_to(ROOT).as_posix():b.sha(p) for p in [*b.OUT.glob('*.asc'),Path(__file__),HERE/'build.py']})
    for p in [HERE/'HOST_CHECKS.json',b.OUT/'HOST_CHECKS.json']:b.write(p,json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='source_sha256'},indent=2))
if __name__=='__main__':main()

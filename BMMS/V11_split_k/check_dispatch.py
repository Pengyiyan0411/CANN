"""Compile actual R23/K1 host policy and four geometry probe predicates."""
from pathlib import Path
import importlib.util,json,shutil,subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;BUILD=HERE/'dispatch_build'
spec=importlib.util.spec_from_file_location('builder',HERE/'build.py');build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)

def function(s,mark):
    i=s.index(mark);start=s.index('{',i);depth=1;j=start+1
    while depth:
        depth+=(s[j]=='{')-(s[j]=='}');j+=1
    return s[i:j]

def source():
    base=build.BASE.read_text(encoding='utf-8');frag=(HERE/'split_k_fragment.asc').read_text(encoding='utf-8')
    policy=build.between(frag,'namespace bmms23 {','template<class T,bool TA,bool TB>\nclass Producer')
    entry=build.between(frag,'template<class T,bool TA,bool TB>\n__aicore__ inline void Entry(', '#endif\n} // namespace bmms23')
    bindings=frag[frag.index('#define BMMS23_KERNEL'):]
    bindings=build.once(bindings,'#define BMMS23_LAUNCH(NAME) NAME<<<p.blocks,nullptr,stream>>>(a,b,y,ws,p)',
        '#define BMMS23_LAUNCH(NAME) do { launchedBlocks=p.blocks; for(bool side:{true,false}){isCube=side; NAME(a,b,y,ws,p);} } while(false)')
    macro=base[base.index('namespace bmms11r2 {'):];res=base[base.index('namespace bmms11d {'):]
    predicates='namespace bmms83 {static inline int32_t UpH(int32_t a,int32_t b){return (a+b-1)/b;}}\n'
    predicates+='namespace bmms11r2 {constexpr int32_t AM=128,BN=256,K1=256;\n'+function(macro,'static inline bool Eligible(')+'\n}\n'
    for name,text in [('r14',base)]+[(n,(build.OUT/(n+'.asc')).read_text(encoding='utf-8')) for n in build.PROBES]:
        part=text[text.index('namespace bmms11d {'):]
        predicates+='namespace '+name+' {\n'+function(part,'static inline bool Eligible(')+'\n'+function(part,'static inline bool ResidualEligible(')+'\n}\n'
    return r'''#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <stdexcept>
#include <array>
#include <vector>
#include <type_traits>
#include <set>
#include <algorithm>
#define __aicore__
#define __global__
#define __mix__(...)
#define __schedmode__(...)
#define ASCEND_IS_AIC (isCube)
#define ASCEND_IS_AIV (!isCube)
using GM_ADDR=uint8_t*;using aclrtStream=void*;
struct half{uint16_t v;};struct bfloat16_t{uint16_t v;};
constexpr int ACL_SUCCESS=0,ACL_MEM_MALLOC_HUGE_FIRST=0;
namespace AscendC {struct TPipe {};}
bool isCube;int producerCalls=0,consumerCalls=0,launches=0,syncs=0,frees=0,launchedBlocks=0;
std::array<int,3> actual{};std::array<int,8> captured{};uint64_t allocated=0;
int aclrtMalloc(void** ptr,uint64_t n,int){*ptr=std::malloc(n);allocated=n;++launches;return *ptr?0:1;}
int aclrtFree(void* ptr){std::free(ptr);++frees;return 0;}
int aclrtSynchronizeStream(void*){++syncs;return 0;}
void need(bool p,const char* msg){if(!p)throw std::runtime_error(msg);}
'''+predicates+policy+r'''
template<class T,bool TA,bool TB>struct Producer{
    void Init(GM_ADDR,GM_ADDR,GM_ADDR,const Plan& p,AscendC::TPipe*){
        actual={std::is_same_v<T,half>?1:2,int(TA),int(TB)};
        captured={p.B,p.M,p.N,p.K,p.mTiles,p.nTiles,p.splits,p.blocks};}
    void Process(){++producerCalls;}
};
struct Consumer{
    void Init(GM_ADDR,GM_ADDR,const Plan& p,AscendC::TPipe*){
        need(captured==std::array<int,8>{p.B,p.M,p.N,p.K,p.mTiles,p.nTiles,p.splits,p.blocks},"producer consumer plan mismatch");}
    void Process(){++consumerCalls;}
};
'''+entry+'}\n'+bindings+r'''
std::set<std::array<int,3>> seen;
uint64_t hostChecks=0,fallbackChecks=0,planChecks=0,selectedPlans=0,partitionChecks=0,probeChecks=0;
bool oracle(int B,int M,int N,int K,int dt,int cores){
    if(B<1||B>64||M<16||M>=128||N<16||N>=256||M%16||N%16||K<4096||K>8192||K%32||
       (dt!=1&&dt!=2)||cores<1||cores>64)return false;
    return 2*B*((M+63)/64)*((N+127)/128)<=cores;
}
void host(int B,int M,int N,int K,int dt,bool ta,bool tb,int cores){
    const bool expected=oracle(B,M,N,K,dt,cores);int before=launches,prod=producerCalls,cons=consumerCalls;
    bool launched=bmms23::TryLaunch(nullptr,nullptr,nullptr,B,M,N,K,dt,ta,tb,cores,nullptr);
    need(launched==expected,"TryLaunch metadata guard mismatch");
    if(!expected){need(launches==before&&prod==producerCalls&&cons==consumerCalls,"fallback launched or allocated");++fallbackChecks;}
    else{
        auto p=bmms23::MakePlan(B,M,N,K,cores);
        if(BMMS23_SINGLE_K_CONTROL){p.splits=1;p.blocks=B*p.mTiles*p.nTiles;}
        need(launches==before+1&&syncs==launches&&frees==launches,"workspace lifecycle mismatch");
        need(producerCalls==prod+1&&consumerCalls==cons+1,"entry branch count mismatch");
        need(actual==std::array<int,3>{dt,int(ta),int(tb)},"dtype layout binding mismatch");
        need(captured==std::array<int,8>{B,M,N,K,p.mTiles,p.nTiles,p.splits,p.blocks},"host launch plan mismatch");
        need(allocated==bmms23::WorkspaceBytes(p)&&launchedBlocks==p.blocks,"workspace or block count mismatch");seen.insert(actual);
    }
    ++hostChecks;
}
void partitions(int B,int M,int N,int K,int cores){
    if(!bmms23::Eligible(B,M,N,K,1,cores))return;
    auto p=bmms23::MakePlan(B,M,N,K,cores);int previous=0,minLen=K,maxLen=0;
    for(int s=0;s<p.splits;++s){int begin=s*(K/32)/p.splits*32,end=(s+1)*(K/32)/p.splits*32;
        need(begin==previous&&end>begin&&begin%32==0&&end%32==0,"K gap overlap or misalignment");
        minLen=std::min(minLen,end-begin);maxLen=std::max(maxLen,end-begin);previous=end;}
    need(previous==K&&minLen>=512&&maxLen-minLen<=32,"K partition coverage or balance mismatch");
    std::vector<int> seenTasks(B*p.mTiles*p.nTiles*p.splits,0);
    for(int group=0;group<p.blocks;++group){int ks=group%p.splits,tile=group/p.splits;
        int nt=tile%p.nTiles,mt=(tile/p.nTiles)%p.mTiles,batch=tile/(p.mTiles*p.nTiles);
        need(batch<B&&mt<p.mTiles&&nt<p.nTiles,"task index outside input");
        need(++seenTasks[((batch*p.mTiles+mt)*p.nTiles+nt)*p.splits+ks]==1,"task collision");}
    for(int count:seenTasks)need(count==1,"missing Cube task");++partitionChecks;
}
int main(){try{
    for(int dt:{1,2})for(bool ta:{false,true})for(bool tb:{false,true}){
        host(1,16,16,4096,dt,ta,tb,20);host(1,112,240,8192,dt,ta,tb,20);
        host(3,80,144,4128,dt,ta,tb,32);host(20,16,16,4096,dt,ta,tb,20);
    }
    need(seen.size()==8,"not all dtype/layout entries reached");
    for(int B:{1,2,3,5,10,20,32,64})for(int cores:{1,2,3,4,8,16,20,24,32,64})
    for(int M=16;M<128;M+=16)for(int N=16;N<256;N+=16)for(int K=4096;K<=8192;K+=32){
        bool eligible=bmms23::Eligible(B,M,N,K,1,cores);need(eligible==oracle(B,M,N,K,1,cores),"plan guard mismatch");++planChecks;
        if(!eligible)continue;auto p=bmms23::MakePlan(B,M,N,K,cores);++selectedPlans;
        int spatial=B*((M+63)/64)*((N+127)/128),cap=std::min({16,cores/spatial,K/512});
        need(p.B==B&&p.M==M&&p.N==N&&p.K==K&&p.mTiles==(M+63)/64&&p.nTiles==(N+127)/128,"plan shape mismatch");
        need(p.splits>=2&&p.splits<=cap&&2*p.splits>cap&&(p.splits&(p.splits-1))==0,"split policy mismatch");
        need(p.blocks==spatial*p.splits&&p.blocks<=cores&&p.blocks<=64,"nonresident Cube plan");
        need(bmms23::WorkspaceBytes(p)<=2097152,"workspace capacity exceeded");
        need(p.splits*16*128*4+16*4+2*M*4+32<=192*1024,"UB capacity exceeded");
        need(r14::ResidualEligible(B,M,N,K,cores)&&!bmms11r2::Eligible(B,M,N,K,cores),"interception outside original R03");
    }
    for(int B:{1,3,10})for(int cores:{2,4,8,20,32,64})for(int M:{16,64,80,112})for(int N:{16,128,144,240})
    for(int K=4096;K<=8192;K+=32)partitions(B,M,N,K,cores);
    for(auto d:std::vector<std::array<int,6>>{
        {0,16,16,4096,1,20},{65,16,16,4096,1,20},{1,0,16,4096,1,20},{1,128,16,4096,1,20},
        {1,16,0,4096,1,20},{1,16,256,4096,1,20},{1,17,16,4096,1,20},{1,16,17,4096,1,20},
        {1,16,16,4064,1,20},{1,16,16,8224,1,20},{1,16,16,4104,1,20},{1,16,16,4096,0,20},
        {1,16,16,4096,3,20},{1,16,16,4096,1,0},{1,16,16,4096,1,65},{1,16,16,4096,1,1}})
        host(d[0],d[1],d[2],d[3],d[4],false,false,d[5]);
    for(int B:{0,1,2,20,65})for(int M:{0,16,17,32,64,80,112,128,256})for(int N:{0,16,17,64,128,144,240,256})
    for(int K:{256,4096,4128,8192,8224})for(int cores:{0,1,20,64,65}){
        bool original=r14::ResidualEligible(B,M,N,K,cores);
        bool scope=M>=16&&M<128&&N>=16&&N<256&&K>=4096&&K<=8192&&M%16==0&&N%16==0&&K%32==0;
        need(G01_B1_OFF::ResidualEligible(B,M,N,K,cores)==(original&&!(scope&&B==1)),"G01 predicate mismatch");
        need(G02_M64_OFF::ResidualEligible(B,M,N,K,cores)==(original&&!(scope&&M<=64)),"G02 predicate mismatch");
        need(G03_N128_OFF::ResidualEligible(B,M,N,K,cores)==(original&&!(scope&&N<=128)),"G03 predicate mismatch");
        need(G04_MN4096_OFF::ResidualEligible(B,M,N,K,cores)==(original&&!(scope&&int64_t(M)*N<=4096)),"G04 predicate mismatch");probeChecks+=4;
    }
    std::cout<<"{\"actual_host_launch_checks\":"<<hostChecks<<",\"unique_device_bindings\":"<<seen.size()
        <<",\"no_launch_fallback_checks\":"<<fallbackChecks<<",\"metadata_plan_checks\":"<<planChecks
        <<",\"selected_plans\":"<<selectedPlans<<",\"K_partition_and_task_checks\":"<<partitionChecks
        <<",\"geometry_probe_checks\":"<<probeChecks<<"}\n";
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
'''

def main():
    build.verify();BUILD.mkdir(exist_ok=True);compiler=shutil.which('g++');assert compiler
    cpp=BUILD/'dispatch.cpp';code=source();build.write(cpp,code);runs={}
    for name,define in [('R23',0),('K1',1)]:
        exe=BUILD/(name+'.exe')
        subprocess.run([compiler,'-std=c++17','-O2','-DBMMS23_SINGLE_K_CONTROL='+str(define),str(cpp),'-o',str(exe)],check=True)
        result=subprocess.run([str(exe)],capture_output=True,text=True,check=True);runs[name]=json.loads(result.stdout)
    bad=build.once(code,'BMMS23_LAUNCH(bmms23_f16_nn);','BMMS23_LAUNCH(bmms23_b16_nn);');build.write(cpp,bad)
    try:
        exe=BUILD/'bad_binding.exe'
        subprocess.run([compiler,'-std=c++17','-O2','-DBMMS23_SINGLE_K_CONTROL=0',str(cpp),'-o',str(exe)],check=True)
        fault=subprocess.run([str(exe)],capture_output=True,text=True)
        assert fault.returncode and 'dtype layout binding mismatch' in fault.stderr
    finally:build.write(cpp,code)
    report={'scope':'actual host and entry bodies with recording stubs, and actual probe eligibility functions; no CANN/NPU compilation',
            'runs':runs,'wrong_dtype_fault_rejected':True,'composition':build.verify(),
            'sources':{p.relative_to(ROOT).as_posix():build.sha(p) for p in [*build.OUT.glob('*.asc'),HERE/'split_k_fragment.asc',Path(__file__)]},
            'cann_compiled_locally':False,'npu_tested_locally':False}
    for p in [HERE/'DISPATCH_CHECKS.json',build.OUT/'DISPATCH_CHECKS.json']:build.write(p,json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()

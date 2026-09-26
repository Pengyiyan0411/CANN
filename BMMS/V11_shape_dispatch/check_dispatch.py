"""Compile actual host selector/launch and all 64 entry bindings with recorders."""
from pathlib import Path
import importlib.util,json,re,shutil,subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;BUILD=HERE/'dispatch_build'
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
build=load('shape_build',HERE/'build.py')
oldbuild=load('resident_build',ROOT/'V11_a_resident/build.py')

def source():
    s=build.BASE.read_text(encoding='utf-8');frag=(HERE/'shape_fragment.asc').read_text(encoding='utf-8')
    prefix=build.between(s,'namespace bmms83 {','constexpr int32_t PACKET_TILES=4;')+'}\n'
    family=oldbuild.between(s,'enum class Family : int32_t {\n    Dot=0,','static inline int32_t MinH(')
    classifier='namespace bmms71 {\n'+oldbuild.function(s,'static inline bool UseResident(')+'\n}\n'
    classifier+='namespace bmmmaxsum_v43 {\n'+oldbuild.function(s,'static inline bool UseTiny(int32_t M, int32_t N, int32_t K)')+'\n}\n'
    classifier+='namespace bmms8 {\n'+family+oldbuild.function(s,'static inline bool IsFixedSmallK(')+'\n'+oldbuild.function(s,'static inline Family Classify(')+'\n}\n'
    policy=(HERE/'host_plan.asc').read_text(encoding='utf-8')
    entry=build.between(frag,'template<class T,bool TA,bool TB,int TK,int TM,int TN,int AM,int BN>\n__aicore__ inline void Entry(', '#endif\n} // namespace bmms22')
    bindings=frag[frag.index('#define BMMS22_KERNEL'):]
    old='#define BMMS22_LAUNCH(NAME) NAME<<<p.blocks,nullptr,stream>>>(a,b,y,ws,partial,p)'
    new='#define BMMS22_LAUNCH(NAME) do { launchedBlocks=p.blocks; for(bool side:{true,false}){isCube=side; NAME(a,b,y,ws,partial,p);} } while(false)'
    bindings=build.once(bindings,old,new)
    return '''#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <stdexcept>
#include <array>
#include <vector>
#include <type_traits>
#include <set>
#include <string>
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
std::array<int,8> actual{};uint64_t allocated=0,partialOffset=0;
int aclrtMalloc(void** ptr,uint64_t n,int){*ptr=std::malloc(n);allocated=n;++launches;return *ptr?0:1;}
int aclrtFree(void* ptr){std::free(ptr);++frees;return 0;}
int aclrtSynchronizeStream(void*){++syncs;return 0;}
void need(bool p,const char* msg){if(!p)throw std::runtime_error(msg);}
'''+prefix+classifier+'namespace bmms22 {\n'+policy+'''
template<class T,bool TA,bool TB,int TK,int TM,int TN,int AM,int BN>struct Producer{
    void Init(GM_ADDR,GM_ADDR,GM_ADDR,const Plan&,AscendC::TPipe*){
        actual={TM,TN,AM,BN,TK,std::is_same_v<T,half>?1:2,int(TA),int(TB)};}
    void Process(){++producerCalls;}
};
template<int TM,int TN,int AM,int BN>struct Consumer{
    void Init(GM_ADDR ring,GM_ADDR part,GM_ADDR,const Plan&,AscendC::TPipe*){
        need(actual[0]==TM&&actual[1]==TN&&actual[2]==AM&&actual[3]==BN,"producer consumer geometry mismatch");
        partialOffset=part-ring;}
    void Process(){++consumerCalls;}
};
'''+entry+'}\n'+bindings+'''
std::set<std::array<int,8>> seen;
int hostChecks=0,fallbackChecks=0,planChecks=0,guardChecks=0,occupancyFallbacks=0;
int routes[4]={};
void host(int B,int M,int N,int K,int dt,bool ta,bool tb,int cores,int want){
    auto selected=bmms22::Select(B,M,N,K,dt,ta,tb,cores);
    need(int(selected.strategy)==want,"expected shape strategy not selected");
    int before=launches,prod=producerCalls,cons=consumerCalls;
    bool launched=bmms22::TryLaunch(nullptr,nullptr,nullptr,B,M,N,K,dt,ta,tb,cores,nullptr);
    need(launched==(want!=0),"TryLaunch return disagrees with selector");
    if(!want){need(launches==before&&prod==producerCalls&&cons==consumerCalls,"fallback launched or allocated");++fallbackChecks;}
    else{
        need(launches==before+1&&syncs==launches&&frees==launches,"workspace lifecycle mismatch");
        need(producerCalls==prod+1&&consumerCalls==cons+1,"missing or repeated entry branch");
        need(actual[4]==K&&actual[5]==dt&&actual[6]==int(ta)&&actual[7]==int(tb),"K dtype layout binding mismatch");
        std::array<int,4> geometry=want==1?std::array<int,4>{64,32,256,32}:want==2?std::array<int,4>{32,256,32,512}:std::array<int,4>{128,128,256,512};
        for(int i=0;i<4;++i)need(actual[i]==geometry[i],"host launched incorrect fixed geometry");
        need(allocated==bmms22::RingBytes(selected)+bmms22::PartialBytes(selected.plan)&&partialOffset==bmms22::RingBytes(selected),"workspace geometry mismatch");
        need(launchedBlocks==selected.plan.blocks,"launch group count mismatch");seen.insert(actual);
    }
    ++hostChecks;
}
int main(){try{
    for(int K:{32,64,128})for(int dt:{1,2})for(bool ta:{false,true})for(bool tb:{false,true}){
        host(1,48,16,K,dt,ta,tb,1,1);host(1,256,128,K,dt,ta,tb,1,3);
        if(K!=128)host(1,32,512,K,dt,ta,tb,1,2);
        host(1,16,256,K,dt,ta,tb,20,0);host(1,128,128,K,dt,ta,tb,20,0);
        host(1,144,256,K,dt,ta,tb,1,0);
    }
    need(seen.size()==64,"not all dtype/layout/K entry points reached");
    for(int B:{1,3,20,64})for(int M:{16,32,48,128,256,272,8192})for(int N:{16,32,128,256,768,8192})
    for(int K:{32,64,128})for(int cores:{1,3,20,64}){
        auto s=bmms22::Select(B,M,N,K,1,false,false,cores);++routes[int(s.strategy)];
        int expected=M>32&&N<=32?1:M<=32&&N>=256&&N%256==0&&K!=128?2:M>=128&&M%128==0&&N>=128&&N%128==0?3:0;
        auto old=bmms83::MakeNative(B,M,N,K,cores);
        if(expected){
            auto larger=expected==1?bmms22::MakePlan<64,32,256>(B,M,N,K,cores):expected==2?bmms22::MakePlan<32,256,32>(B,M,N,K,cores):bmms22::MakePlan<128,128,256>(B,M,N,K,cores);
            if(larger.blocks<old.blocks){expected=0;++occupancyFallbacks;}
        }
        need(int(s.strategy)==expected,"shape boundary/occupancy guard mismatch");
        if(expected){
            const auto p=s.plan;int tm=expected==2?32:expected==3?128:64,tn=expected==1?32:expected==2?256:128;
            need(p.B==B&&p.M==M&&p.N==N&&p.K==K&&p.mTiles==(M+tm-1)/tm&&p.nTiles==(N+tn-1)/tn,"shape plan dimensions mismatch");
            need(p.tasks==B*p.pM*p.pN&&p.blocks<=cores&&p.blocks<=p.tasks&&p.blocks>=old.blocks,"shape plan launch mismatch");
            int coveredM=0,coveredN=0;
            for(int i=0;i<p.pM;++i){int q=(i+1)*p.mTiles/p.pM-i*p.mTiles/p.pM;need(q>0,"empty M partition");coveredM+=q;}
            for(int i=0;i<p.pN;++i){int q=(i+1)*p.nTiles/p.pN-i*p.nTiles/p.pN;need(q>0,"empty N partition");coveredN+=q;}
            need(coveredM==p.mTiles&&coveredN==p.nTiles,"shape partition gap");
        }
        ++planChecks;
    }
    for(auto bad:std::vector<std::array<int,7>>{
        {0,256,256,64,1,1,0},{65,256,256,64,1,1,0},{1,256,256,64,0,1,0},
        {1,256,256,64,3,1,0},{1,256,256,64,1,0,0},{1,256,256,64,1,65,0},
        {1,255,256,64,1,1,0},{1,256,255,64,1,1,0},{1,256,256,16,1,1,0},
        {1,256,256,256,1,1,0},{1,8208,256,64,1,1,0},{1,16,16,32,1,1,0},
        {1,0,256,64,1,1,0},{1,256,0,64,1,1,0}}){
        host(bad[0],bad[1],bad[2],bad[3],bad[4],false,false,bad[5],0);++guardChecks;
    }
    need(occupancyFallbacks>0&&routes[1]>0&&routes[2]>0&&routes[3]>0,"selector coverage missing");
    std::cout<<"{\\\"actual_host_launch_checks\\\":"<<hostChecks<<",\\\"unique_device_bindings\\\":"<<seen.size()
        <<",\\\"no_launch_fallback_checks\\\":"<<fallbackChecks<<",\\\"metadata_plan_checks\\\":"<<planChecks
        <<",\\\"invalid_guard_checks\\\":"<<guardChecks<<",\\\"occupancy_fallbacks\\\":"<<occupancyFallbacks
        <<",\\\"route_counts\\\":["<<routes[0]<<","<<routes[1]<<","<<routes[2]<<","<<routes[3]<<"]}\\n";
}catch(const std::exception&e){std::cerr<<e.what()<<"\\n";return 1;}}
'''

def main():
    build.verify();BUILD.mkdir(exist_ok=True);cpp=BUILD/'dispatch.cpp';code=source();build.write(cpp,code);exe=BUILD/'dispatch.exe'
    compiler=shutil.which('g++');assert compiler
    subprocess.run([compiler,'-std=c++17','-O2',str(cpp),'-o',str(exe)],check=True)
    result=subprocess.run([str(exe)],capture_output=True,text=True,check=True);data=json.loads(result.stdout)
    # Rewire one actual host binding to another dtype: the checker must detect it.
    bad=build.once(code,'BMMS22_LAUNCH(bmms22_sn_f16_nn_k32);','BMMS22_LAUNCH(bmms22_sn_b16_nn_k32);')
    build.write(cpp,bad)
    try:
        subprocess.run([compiler,'-std=c++17','-O2',str(cpp),'-o',str(BUILD/'bad_dispatch.exe')],check=True)
        fault=subprocess.run([str(BUILD/'bad_dispatch.exe')],capture_output=True,text=True)
        assert fault.returncode and 'K dtype layout binding mismatch' in fault.stderr
    finally:build.write(cpp,code)
    data.update(scope='actual host policy, workspace sizing, launch bindings and entry bodies with recording stubs; no CANN/NPU compile',
                wrong_dtype_fault_rejected=True,cann_compiled_locally=False,npu_tested_locally=False,
                sources={str(p.relative_to(ROOT).as_posix()):build.sha(p) for p in [build.BASE,build.OUT/(build.NAME+'.asc'),Path(__file__)]})
    build.write(HERE/'DISPATCH_CHECKS.json',json.dumps(data,indent=2)+'\n');print(json.dumps(data,indent=2))
if __name__=='__main__':main()

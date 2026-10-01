from pathlib import Path
root=Path(__file__).resolve().parents[1];h=root/'V12_npu_lab/harness'
helper=r'''
namespace c12lab {
using Plan=bmms11r2::Plan;
static inline bool Eligible(int B,int M,int N,int K,int cores){
 return B==1&&M>=1024&&N>=1024&&K>=1536&&K<2048&&cores>=2&&bmms11r2::Eligible(B,M,N,K,cores);
}
static inline Plan PacketPlan(Plan p,int cores,int packetN){
 p.pM=p.mTiles;p.pN=(p.nTiles+packetN-1)/packetN;
 p.tasks=p.B*p.pM*p.pN;p.blocks=bmms83::MinH(cores,p.tasks);return p;
}
}
'''
(h/'c12_plans.h').write_text(helper,encoding='utf-8',newline='\n')
s=(h/'event_bench.asc').read_text(encoding='utf-8')
s=s.replace('#undef main','#undef main\n#include "c12_plans.h"\nstatic int c12Cores=0,c12PacketN=2;')
s=s.replace('auto p=plan;','auto p=candidate?c12lab::PacketPlan(plan,c12Cores,c12PacketN):plan;')
s=s.replace('if(candidate){DISPATCH(bmms1207);}else{DISPATCH(bmms11r2);}','DISPATCH(bmms11r2);')
s=s.replace('batchCalls=64','batchCalls=32')
s=s.replace('int id,dt,ta,tb;', 'c12Cores=int(cores);if(const char* x=std::getenv("C12_PACKET_N"))c12PacketN=std::atoi(x);\n    if(c12PacketN<1||c12PacketN>4)return 2;\n    int id,dt,ta,tb;')
s=s.replace('bmms1207::Eligible','c12lab::Eligible')
s=s.replace('bmms11r2::WorkspaceBytes(p),ACL_MEM', 'bmms11r2::WorkspaceBytes(p)+bmms11r2::WorkspaceBytes(c12lab::PacketPlan(p,cores,c12PacketN)),ACL_MEM')
s=s.replace('candidate?"r07":"r03"','candidate?"packet":"r19"')
s=s.replace('const auto p=bmms11r2::MakePlan(B,M,N,K,cores);','const auto p=bmms11r2::MakePlan(B,M,N,K,cores);\n        const auto q=c12lab::PacketPlan(p,cores,c12PacketN);\n        std::printf("PLAN %d base=%d,%d,%d,%d packet=%d,%d,%d,%d\\n",id,p.pM,p.pN,p.tasks,p.blocks,q.pM,q.pN,q.tasks,q.blocks);')
warm='        for(int warm=0;warm<100;++warm)'
precision=r'''        // Independent correctness gate before collecting any timings.
        for(int v=0;v<2;++v){
          ck(aclrtMemcpy(y,B*4,poison.data(),B*4,ACL_MEMCPY_HOST_TO_DEVICE),"poison verify");
          launch_direct(v!=0,a,b,y,ws,p,dt,ta,tb,stream);
          ck(aclrtSynchronizeStreamWithTimeout(stream,10000),"verify sync");
          ck(aclrtMemcpy(got.data(),B*4,y,B*4,ACL_MEMCPY_DEVICE_TO_HOST),"verify output");
          for(int j=0;j<B;++j)if(!std::isfinite(got[j])||std::fabs(double(got[j])-golden[j])>1e-4+1e-4*std::fabs(golden[j]))return 3;
        }
'''
assert warm in s;s=s.replace(warm,precision+warm)
(h/'event_c12_plan.asc').write_text(s,encoding='utf-8',newline='\n')
cm=h/'CMakeLists.txt';t=cm.read_text(encoding='utf-8')
if 'add_executable(event_c12_plan ' not in t:
 t+='''
add_executable(event_c12_plan event_c12_plan.asc)
target_compile_definitions(event_c12_plan PRIVATE BMMS_KERNEL_HEADER="r19.asc" BMMS_VARIANT="r19")
target_link_libraries(event_c12_plan PRIVATE tiling_api register platform unified_dlog dl m graph_base)
target_include_directories(event_c12_plan PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_options(event_c12_plan PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=${NPU_ARCH}>)
'''
cm.write_text(t,encoding='utf-8',newline='\n')
g=(h/'generate_c8_final.py').read_text(encoding='utf-8')
a=g.index('import random');b=g.index('manifest=[];records=[]')
spec='''specs=[]
shapes=[(1024,1024,1536),(1040,2064,1568),(1536,2048,1664),(2048,2048,1792),(3072,1536,1920),(4096,3072,2016),(8192,1040,1632),(1056,8192,1984)]
for j,(M,N,K) in enumerate(shapes):
 for ta,tb in itertools.product([0,1],[0,1]):
  specs.append(dict(id=len(specs),label='c12_plan_screen',B=1,M=M,N=N,K=K,dtype=1+j%2,ta=ta,tb=tb,pattern='random'))
'''
g=g[:a]+spec+g[b:];g=g.replace('cases_c8_final','cases_c12_screen').replace('1830928','200928')
g=g.replace("sets={'manifest':range(len(manifest))}","sets={'manifest':range(len(manifest)),'profile':[12]}")
(h/'generate_c12_screen.py').write_text(g,encoding='utf-8',newline='\n')
script='''#!/usr/bin/env bash
set -eo pipefail
cd /home/developer/bmms_v12_lab_20260928
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cmake -S . -B build >logs/c12_configure.log 2>&1
cmake --build build --target event_c12_plan -j3 >logs/c12_plan_build.log 2>&1
python3 generate_c12_screen.py >results/c12_generate.log 2>&1
./build/bench_r19 cases_c12_screen/manifest.txt 3 results/c12_r19_correctness.jsonl >results/c12_r19_correctness.log 2>&1
C12_PACKET_N=2 ./build/event_c12_plan cases_c12_screen/manifest.txt 6 results/c12_packet2_event.jsonl >results/c12_packet2_event.log 2>&1
C12_PACKET_N=1 ./build/event_c12_plan cases_c12_screen/manifest.txt 6 results/c12_packet1_event.jsonl >results/c12_packet1_event.log 2>&1
echo C12_SCREEN_DONE
'''
(h/'screen_c12.sh').write_text(script,encoding='utf-8',newline='\n')
print('C12 synthetic screen prepared')

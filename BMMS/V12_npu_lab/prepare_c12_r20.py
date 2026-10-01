from pathlib import Path
import json,hashlib
r=Path(__file__).resolve().parents[1];o=r/'BMMS_V12';h=r/'V12_npu_lab/harness'
base=(o/'v12_baseline_r19.asc').read_bytes();text=base.decode('utf-8')
helper=r'''
// BMMS1220_BEGIN
namespace bmms1220 {
using Plan=bmms11r2::Plan;
static inline bool Eligible(int B,int M,int N,int K,int cores){
    return B==1&&M>=1024&&N>=1024&&K>=1536&&K<2048&&cores>=2&&
        bmms11r2::Eligible(B,M,N,K,cores);
}
static inline Plan MakePlan(int B,int M,int N,int K,int cores){
    const Plan base=bmms11r2::MakePlan(B,M,N,K,cores);
    if(!Eligible(B,M,N,K,cores))return base;
    Plan p=base;p.pM=p.mTiles;p.pN=p.nTiles;
    p.tasks=p.B*p.pM*p.pN;p.blocks=bmms83::MinH(cores,p.tasks);
    // Compare actual per-core task assignments, including the original short
    // second wave and partial macro tiles. No assumption about exact shape.
    const auto a=bmms11r2::ExistingPeak(base),b=bmms11r2::ExistingPeak(p);
    if(10*b.tiles<=9*a.tiles&&b.cells<=a.cells&&b.input<=a.input)return p;
    return base;
}
static inline bool Changed(const Plan& a,const Plan& b){
    return a.pM!=b.pM||a.pN!=b.pN||a.tasks!=b.tasks||a.blocks!=b.blocks;
}
static inline bool TryLaunch(GM_ADDR a,GM_ADDR b,GM_ADDR y,int B,int M,int N,int K,
    int dtype,bool ta,bool tb,int cores,aclrtStream stream){
    if((dtype!=1&&dtype!=2)||!Eligible(B,M,N,K,cores))return false;
    const auto p=MakePlan(B,M,N,K,cores);
    uint8_t* ws=nullptr;
    if(aclrtMalloc(reinterpret_cast<void**>(&ws),bmms11r2::WorkspaceBytes(p),ACL_MEM_MALLOC_HUGE_FIRST)!=ACL_SUCCESS)return false;
    auto partial=ws+bmms11r2::RingBytes(p);
#define BMMS1220_LAUNCH(NAME) NAME<<<p.blocks,nullptr,stream>>>(a,b,y,ws,partial,p)
    if(dtype==1){
        if(!ta&&!tb){BMMS1220_LAUNCH(bmms11r2_f16_nn);}else if(!ta&&tb){BMMS1220_LAUNCH(bmms11r2_f16_nt);}
        else if(ta&&!tb){BMMS1220_LAUNCH(bmms11r2_f16_tn);}else{BMMS1220_LAUNCH(bmms11r2_f16_tt);}
    }else{
        if(!ta&&!tb){BMMS1220_LAUNCH(bmms11r2_b16_nn);}else if(!ta&&tb){BMMS1220_LAUNCH(bmms11r2_b16_nt);}
        else if(ta&&!tb){BMMS1220_LAUNCH(bmms11r2_b16_tn);}else{BMMS1220_LAUNCH(bmms11r2_b16_tt);}
    }
#undef BMMS1220_LAUNCH
    if(aclrtSynchronizeStream(stream)!=ACL_SUCCESS)std::abort();if(aclrtFree(ws)!=ACL_SUCCESS)std::abort();return true;
}
}
// BMMS1220_END

'''
hook='    if(bmms1220::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
idx=text.index('extern "C" void run_kernel') if 'extern "C" void run_kernel' in text else text.index('void run_kernel')
# Insert before the public entry, preserving every original byte including CRLF.
module=helper.encode();out=base[:idx]+module+base[idx:]
needle=b'    if(bmms11r2::TryLaunch(a,b,y,'
pos=out.index(needle);out=out[:pos]+hook.encode()+out[pos:]
assert out.replace(module,b'',1).replace(hook.encode(),b'',1)==base
src=o/'v12_r20_case12_packet_plan.asc';src.write_bytes(out);(h/'r20.asc').write_bytes(out)
manifest=dict(candidate=src.name,parent='v12_baseline_r19.asc',parent_sha256=hashlib.sha256(base).hexdigest(),sha256=hashlib.sha256(out).hexdigest(),parent_recovered_byte_for_byte=True,status='NPU validation pending',change='host-only single-macro round-robin plan; 10% peak macro reduction plus no increase in peak cells/input')
(o/'v12_r20_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
s=(h/'event_c12_plan.asc').read_text(encoding='utf-8')
s=s.replace('static int c12Cores=0,c12PacketN=2;','static int c12Cores=0,c12PacketN=2;\nstatic bmms11r2::Plan c12Chosen;')
s=s.replace('c12lab::PacketPlan(plan,c12Cores,c12PacketN)','c12Chosen')
s=s.replace('c12lab::PacketPlan(p,cores,c12PacketN)','bmms1220::MakePlan(B,M,N,K,cores)')
s=s.replace('const auto q=bmms1220::MakePlan(B,M,N,K,cores);','const auto q=bmms1220::MakePlan(B,M,N,K,cores);c12Chosen=q;')
s=s.replace('candidate?"packet":"r19"','(candidate&&bmms1220::Changed(p,q))?"r20":"r19"')
(h/'event_bench_r20.asc').write_text(s,encoding='utf-8',newline='\n')
cm=h/'CMakeLists.txt';t=cm.read_text(encoding='utf-8')
if 'add_executable(bench_r20 ' not in t:
 t+='''
add_executable(bench_r20 main.asc)
add_executable(event_bench_r20 event_bench_r20.asc)
add_executable(sanitize_r20 main.asc)
foreach(t IN ITEMS bench_r20 event_bench_r20 sanitize_r20)
  target_compile_definitions(${t} PRIVATE BMMS_KERNEL_HEADER="r20.asc" BMMS_VARIANT="r20")
  target_link_libraries(${t} PRIVATE tiling_api register platform unified_dlog dl m graph_base)
  target_include_directories(${t} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
  target_compile_options(${t} PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=${NPU_ARCH}>)
endforeach()
target_compile_options(sanitize_r20 PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--cce-enable-sanitizer> $<$<COMPILE_LANGUAGE:ASC>:-gline-tables-only>)
add_custom_target(c12_r20_build DEPENDS bench_r20 event_bench_r20 sanitize_r20)
'''
cm.write_text(t,encoding='utf-8',newline='\n')
g=(h/'generate_c12_screen.py').read_text(encoding='utf-8');a=g.index('specs=[]');b=g.index('manifest=[];records=[]')
spec='''specs=[]
import random
rng=random.Random(2092801)
shapes=[(1152,1280,1600),(1280,1536,1728),(1792,2560,1824),(2304,1280,1952),(2560,3072,1632),(3584,2048,1888),(4112,1040,1760),(1040,4112,2016),(2048,8192,1536),(8192,2048,1984),(8192,8192,1664),(1024,8192,1568)]
for j,(M,N,K) in enumerate(shapes):
 for t in range(2):
  layout=(j+t*2)%4
  specs.append(dict(id=len(specs),label='c12_fresh_holdout',B=1,M=M,N=N,K=K,dtype=1+t,ta=layout//2,tb=layout%2,pattern='random'))
for j,pattern in enumerate(['zero','negative','wide_scale','equal_columns']):
 for dt in [1,2]:
  specs.append(dict(id=len(specs),label='c12_value',B=1,M=1040,N=1296,K=1568,dtype=dt,ta=j//2,tb=j%2,pattern=pattern))
'''
g=g[:a]+spec+g[b:];g=g.replace('cases_c12_screen','cases_c12_holdout').replace('200928','2092802');g=g.replace("'profile':[12]","'profile':[4], 'sanitize':[6,7], 'screen':range(24)")
(h/'generate_c12_holdout.py').write_text(g,encoding='utf-8',newline='\n')
script='''#!/usr/bin/env bash
set -eo pipefail
cd /home/developer/bmms_v12_lab_20260928
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cmake -S . -B build >logs/c12_r20_configure.log 2>&1
cmake --build build --target c12_r20_build -j3 >logs/c12_r20_build.log 2>&1
python3 generate_c12_holdout.py >results/c12_holdout_generate.log 2>&1
./build/bench_r20 cases_c12_screen/manifest.txt 3 results/c12_r20_screen_correctness.jsonl >results/c12_r20_screen_correctness.log 2>&1
./build/bench_r19 cases_c12_holdout/manifest.txt 3 results/c12_r19_holdout_correctness.jsonl >results/c12_r19_holdout_correctness.log 2>&1
./build/bench_r20 cases_c12_holdout/manifest.txt 3 results/c12_r20_holdout_correctness.jsonl >results/c12_r20_holdout_correctness.log 2>&1
./build/event_bench_r20 cases_c12_holdout/screen.txt 10 results/c12_r20_holdout_event.jsonl >results/c12_r20_holdout_event.log 2>&1
./build/event_bench_r20 cases_c12_holdout/screen.txt 10 results/c12_r20_holdout_event_repeat.jsonl >results/c12_r20_holdout_event_repeat.log 2>&1
BMMS_EVENT_AA=1 ./build/event_bench_r20 cases_c12_screen/profile.txt 6 results/c12_r20_aa.jsonl >results/c12_r20_aa.log 2>&1
echo C12_R20_DONE
'''
(h/'check_c12_r20.sh').write_text(script,encoding='utf-8',newline='\n')
print(src.name,manifest['sha256'])

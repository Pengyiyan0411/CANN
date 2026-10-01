from pathlib import Path
import hashlib,json
r=Path(__file__).resolve().parents[1];o=r/'BMMS_V12';h=r/'V12_npu_lab/harness'
base=(o/'v12_baseline_r19.asc').read_bytes()
module=r'''
// BMMS1222_BEGIN
namespace bmms1222 {
using Plan=bmms1219::RaggedPlan;
static inline bool Eligible(int B,int M,int N,int K,int dtype,int cores){
    return B==1&&M>=1024&&M<2048&&N>=2048&&N<=8192&&K>=1536&&K<4096&&
      (dtype==1||dtype==2)&&bmms11r2::Eligible(B,M,N,K,cores);
}
static inline bool Prefer(int M,int N,int K,bool ta,bool tb){
    // Same physical ND-pitch criterion as accepted r19. Packing is not free:
    // preserve R06 when both expensive conversion pitches are 128B aligned.
    return (ta&&M%64!=0)||((tb?K:N)%64!=0);
}
static inline bool ValidPlan(const Plan& p,int cores){
    const auto& c=p.cube;
    return c.B==1&&c.M==p.realM&&c.N==p.realN&&c.K==p.realK&&
      c.M>=1024&&c.M<2048&&c.N>=2048&&c.N<=8192&&c.K>=1536&&c.K<4096&&
      c.M%16==0&&c.N%16==0&&c.K%32==0&&
      c.pM>=1&&c.pM<=c.mTiles&&c.pN>=1&&c.pN<=c.nTiles&&
      c.tasks==c.pM*c.pN&&c.blocks>=1&&c.blocks<=cores&&c.blocks<=c.tasks&&
      bmms1219::WorkspaceBytes(p)<=bmms1219::MAX_WORKSPACE_BYTES&&
      bmms1219::AppUbBytes(p)<=bmms1219::UB_BUDGET_BYTES;
}
static inline bool TryLaunch(GM_ADDR a,GM_ADDR b,GM_ADDR y,int B,int M,int N,int K,
    int dtype,bool ta,bool tb,int cores,aclrtStream stream){
    if(!Eligible(B,M,N,K,dtype,cores)||!Prefer(M,N,K,ta,tb))return false;
    const auto p=bmms1219::MakePlan(M,N,K,cores,ta,tb);
    if(!bmms1222::ValidPlan(p,cores))return false;
    uint8_t* ws=nullptr;
    if(aclrtMalloc(reinterpret_cast<void**>(&ws),bmms1219::WorkspaceBytes(p),ACL_MEM_MALLOC_HUGE_FIRST)!=ACL_SUCCESS)return false;
    auto ap=ws;auto bp=ap+bmms1219::ABytes(p);auto ring=bp+bmms1219::BBytes(p);auto part=ring+bmms1219::RingBytes(p);
#define BMMS1222_CALL(NAME) NAME<<<p.cube.blocks,nullptr,stream>>>(a,b,y,ap,bp,ring,part,p)
    if(dtype==1){
      if(!ta&&!tb){BMMS1222_CALL(bmms1219_f16_nn);}else if(!ta&&tb){BMMS1222_CALL(bmms1219_f16_nt);}
      else if(ta&&!tb){BMMS1222_CALL(bmms1219_f16_tn);}else{BMMS1222_CALL(bmms1219_f16_tt);}
    }else{
      if(!ta&&!tb){BMMS1222_CALL(bmms1219_b16_nn);}else if(!ta&&tb){BMMS1222_CALL(bmms1219_b16_nt);}
      else if(ta&&!tb){BMMS1222_CALL(bmms1219_b16_tn);}else{BMMS1222_CALL(bmms1219_b16_tt);}
    }
#undef BMMS1222_CALL
    if(aclrtSynchronizeStream(stream)!=ACL_SUCCESS)std::abort();
    if(aclrtFree(ws)!=ACL_SUCCESS)std::abort();return true;
}
}
// BMMS1222_END

'''.encode()
idx=base.index(b'extern "C" void run_kernel');out=base[:idx]+module+base[idx:]
hook=b'    if(bmms1222::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
idx=out.index(b'    if(bmms11r2::TryLaunch(a,b,y,');out=out[:idx]+hook+out[idx:]
assert out.replace(module,b'',1).replace(hook,b'',1)==base
src=o/'v12_r22_dense_nz_pitch.asc';src.write_bytes(out);(h/'r22.asc').write_bytes(out)
manifest=dict(candidate=src.name,parent='v12_baseline_r19.asc',sha256=hashlib.sha256(out).hexdigest(),parent_sha256=hashlib.sha256(base).hexdigest(),status='validation pending',change='Reuse r19 NZ device kernels for aligned M1K-2K N2K-8K K1.5K-4K only with non128B expensive ND pitches; original planner and all device code retained')
(o/'v12_r22_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
t=(h/'event_c1112_nz.asc').read_text(encoding='utf-8')
t=t.replace('    if(candidate){','    candidate=candidate&&bmms1222::Prefer(plan.M,plan.N,plan.K,ta,tb);\n    if(candidate){',1)
t=t.replace('candidate?"nz":"nd"','(candidate&&bmms1222::Prefer(p.M,p.N,p.K,ta,tb))?"nz":"nd"')
(h/'event_bench_r22.asc').write_text(t,encoding='utf-8',newline='\n')
cm=h/'CMakeLists.txt';t=cm.read_text(encoding='utf-8')
if 'add_executable(bench_r22 ' not in t:
 a=t.index('add_executable(bench_r21 ');b=t.index('add_executable(event_c1112_nz ',a)
 t+='\n'+t[a:b].replace('r21','r22').replace('c12_r22_build','c1112_r22_build')
cm.write_text(t,encoding='utf-8',newline='\n')
g=(h/'generate_c1112_screen.py').read_text(encoding='utf-8').replace('cases_c1112_screen','cases_c1112_holdout').replace('2092812','2092822').replace('2092811','2092821')
a=g.index('shapes=');b=g.index('for j,(M,N,K)',a)
g=g[:a]+'''shapes=[(1152,3072,1600),(1168,3072,1600),(1152,3088,1600),(1152,3072,1632),
        (1296,5120,1728),(1280,5136,1696),(1792,6144,1728),(1808,6160,1760),
        (1168,3072,2176),(1152,3088,2176),(1152,3072,2208),(1296,5120,2816),
        (1280,5136,2592),(1792,6144,3584),(1808,6160,3552),(1920,8192,3936)]
'''+g[b:]
a=g.index('for j,pattern in enumerate');b=g.index('manifest=[];records=[]',a);g=g[:a]+g[b:]
g=g.replace("'profile':[4], 'sanitize':[34,35], 'screen':range(32)","'profile':[6], 'sanitize':[6,7], 'screen':range(64)")
g=g.replace("label='c1112_nz_screen'","label='c1112_frozen_policy_holdout'")
(h/'generate_c1112_holdout.py').write_text(g,encoding='utf-8',newline='\n')
script='''#!/usr/bin/env bash
set -eo pipefail
cd /home/developer/bmms_v12_lab_20260928
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cmake -S . -B build >logs/c1112_r22_configure.log 2>&1
cmake --build build --target c1112_r22_build -j3 >logs/c1112_r22_build.log 2>&1
python3 generate_c1112_holdout.py >results/c1112_holdout_generate.log 2>&1
for pair in 'screen cases_c1112_screen' 'holdout cases_c1112_holdout' 'original cases' 'c8 cases_c8_final' 'split cases_split' 'controls cases_split_controls'; do
 read -r label dir <<< "$pair"
 ./build/bench_r22 "$dir/manifest.txt" 3 "results/c1112_r22_${label}_correctness.jsonl" >"results/c1112_r22_${label}_correctness.log" 2>&1
done
./build/event_bench_r22 cases_c1112_screen/screen.txt 8 results/c1112_r22_screen_event.jsonl >results/c1112_r22_screen_event.log 2>&1
./build/event_bench_r22 cases_c1112_holdout/screen.txt 8 results/c1112_r22_holdout_event.jsonl >results/c1112_r22_holdout_event.log 2>&1
./build/event_bench_r22 cases_c1112_holdout/screen.txt 8 results/c1112_r22_holdout_event_repeat.jsonl >results/c1112_r22_holdout_event_repeat.log 2>&1
python3 analyze_c1112.py >results/c1112_r22_event_analysis.log
echo C1112_R22_CHECK_DONE
'''
(h/'check_c1112_r22.sh').write_text(script,encoding='utf-8',newline='\n')
print(src.name,manifest['sha256'])

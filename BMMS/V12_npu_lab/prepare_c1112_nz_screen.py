from pathlib import Path
r=Path(__file__).resolve().parent;h=r/'harness';d=r/'host_c1112';d.mkdir(exist_ok=True)
t=(h/'event_bench_r21.asc').read_text(encoding='utf-8')
start=t.index('#include "c12_plans.h"');end=t.index('\nint main(',start)
launch=r'''static bmms1219::RaggedPlan nzPlan;
static bool eligible(int B,int M,int N,int K,int dt,int cores){
    return B==1&&M>=1024&&M<2048&&N>=2048&&N<=8192&&K>=1536&&K<4096&&
      (dt==1||dt==2)&&bmms11r2::Eligible(B,M,N,K,cores);
}
static void launch_direct(bool candidate,void* a,void* b,void* y,void* ws,
    const bmms11r2::Plan& plan,int dt,bool ta,bool tb,aclrtStream stream){
    if(candidate){
      auto p=nzPlan;auto ap=(uint8_t*)ws;auto bp=ap+bmms1219::ABytes(p);
      auto ring=bp+bmms1219::BBytes(p);auto part=ring+bmms1219::RingBytes(p);
#define CALL(NAME) NAME<<<p.cube.blocks,nullptr,stream>>>((uint8_t*)a,(uint8_t*)b,(uint8_t*)y,ap,bp,ring,part,p)
      if(dt==1){if(!ta&&!tb){CALL(bmms1219_f16_nn);}else if(!ta&&tb){CALL(bmms1219_f16_nt);}else if(ta&&!tb){CALL(bmms1219_f16_tn);}else{CALL(bmms1219_f16_tt);}}
      else{if(!ta&&!tb){CALL(bmms1219_b16_nn);}else if(!ta&&tb){CALL(bmms1219_b16_nt);}else if(ta&&!tb){CALL(bmms1219_b16_tn);}else{CALL(bmms1219_b16_tt);}}
#undef CALL
    }else{
      auto p=plan;auto ring=(uint8_t*)ws;auto part=ring+bmms11r2::RingBytes(p);
#define CALL(NAME) NAME<<<p.blocks,nullptr,stream>>>((uint8_t*)a,(uint8_t*)b,(uint8_t*)y,ring,part,p)
      if(dt==1){if(!ta&&!tb){CALL(bmms11r2_f16_nn);}else if(!ta&&tb){CALL(bmms11r2_f16_nt);}else if(ta&&!tb){CALL(bmms11r2_f16_tn);}else{CALL(bmms11r2_f16_tt);}}
      else{if(!ta&&!tb){CALL(bmms11r2_b16_nn);}else if(!ta&&tb){CALL(bmms11r2_b16_nt);}else if(ta&&!tb){CALL(bmms11r2_b16_tn);}else{CALL(bmms11r2_b16_tt);}}
#undef CALL
    }
}
'''
t=t[:start]+launch+t[end:]
a=t.index('    c12Cores=');b=t.index('    int id,dt,ta,tb;',a);t=t[:a]+t[b:]
t=t.replace('!c12lab::Eligible(B,M,N,K,cores)','!eligible(B,M,N,K,dt,cores)')
a=t.index('        const auto q=');b=t.index('        auto prefix=',a)
t=t[:a]+'''        nzPlan=bmms1219::MakePlan(M,N,K,cores,ta,tb);
        if(bmms1219::WorkspaceBytes(nzPlan)>bmms1219::MAX_WORKSPACE_BYTES||bmms1219::AppUbBytes(nzPlan)>bmms1219::UB_BUDGET_BYTES)return 4;
'''+t[b:]
t=t.replace('bmms11r2::WorkspaceBytes(p)+bmms11r2::WorkspaceBytes(bmms1221::MakePlan(B,M,N,K,cores))','bmms11r2::WorkspaceBytes(p)+bmms1219::WorkspaceBytes(nzPlan)')
t=t.replace('(candidate&&bmms1221::Changed(p,q))?"r21":"r19"','candidate?"nz":"nd"')
assert 'c12Chosen' not in t and 'bmms1221' not in t and 'WorkspaceBytes(q)' not in t
(h/'event_c1112_nz.asc').write_text(t,encoding='utf-8',newline='\n')
g=(h/'generate_c12_holdout.py').read_text(encoding='utf-8').replace('cases_c12_holdout','cases_c1112_screen').replace('2092802','2092812').replace('2092801','2092811')
a=g.index('shapes=');b=g.index('manifest=[];records=[]',a)
g=g[:a]+'''shapes=[(1024,2048,1536),(1040,2064,1568),(1536,4096,1664),(2032,8192,1760),
        (1024,2048,2048),(1040,2064,2080),(1536,4096,3072),(2032,8192,4064)]
for j,(M,N,K) in enumerate(shapes):
 for layout in range(4):
  specs.append(dict(id=len(specs),label='c1112_nz_screen',B=1,M=M,N=N,K=K,dtype=1+(j+layout)%2,ta=layout//2,tb=layout%2,pattern='random'))
for j,pattern in enumerate(['zero','negative','wide_scale','equal_columns']):
 for dt in [1,2]:
  specs.append(dict(id=len(specs),label='c1112_value',B=1,M=1040,N=2064,K=1568,dtype=dt,ta=j//2,tb=j%2,pattern=pattern))
'''+g[b:]
g=g.replace("'profile':[4], 'sanitize':[6,7], 'screen':range(24)","'profile':[4], 'sanitize':[34,35], 'screen':range(32)")
(h/'generate_c1112_screen.py').write_text(g,encoding='utf-8',newline='\n')
p=h/'CMakeLists.txt';cm=p.read_text(encoding='utf-8')
if 'add_executable(event_c1112_nz ' not in cm:
 a=cm.index('add_executable(event_c12_plan ');b=cm.index('add_executable(bench_r20 ',a)
 cm+='\n'+cm[a:b].replace('event_c12_plan','event_c1112_nz')
p.write_text(cm,encoding='utf-8',newline='\n')
script='''#!/usr/bin/env bash
set -eo pipefail
cd /home/developer/bmms_v12_lab_20260928
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cmake -S . -B build >logs/c1112_configure.log 2>&1
cmake --build build --target event_c1112_nz -j2 >logs/c1112_build.log 2>&1
python3 generate_c1112_screen.py >results/c1112_generate.log 2>&1
./build/bench_r19 cases_c1112_screen/manifest.txt 3 results/c1112_r19_correctness.jsonl >results/c1112_r19_correctness.log 2>&1
./build/event_c1112_nz cases_c1112_screen/manifest.txt 6 results/c1112_nz_screen.jsonl >results/c1112_nz_screen.log 2>&1
echo C1112_NZ_SCREEN_DONE
'''
(h/'screen_c1112.sh').write_text(script,encoding='utf-8',newline='\n')
print('screen prepared')

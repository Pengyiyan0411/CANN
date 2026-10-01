from pathlib import Path
import json,hashlib,subprocess
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'V12_npu_lab/results/case12_k1_20261001'
base=(ROOT/'BMMS_V12/v12_baseline_r41.asc').read_bytes().decode()
src=(ROOT/'BMMS_V12/v12_r53_case12_m256_prefetch.asc').read_bytes().decode()
a=src.index('// BMMS1253_BEGIN');b=src.index('// BMMS1253_END',a)+len('// BMMS1253_END\n\n')
hook='    if(bmms1253::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
assert (src[:a]+src[b:]).replace(hook,'',1)==base
prefix=(OUT/'host_guard.cpp').read_text().split('namespace bmms1251 {')[0]
a=src.index('namespace bmms1253 {');b=src.index('template<class T,bool TA,bool TB>',a)
prefix+=src[a:b]+'}\n'
code=prefix+r'''
int main(){int active=0,active20=0;long long partials=0;
for(int cores=1;cores<=64;++cores)for(int M=1280;M<1536;M+=16)
for(int N=4096;N<6144;N+=64)for(int ta=0;ta<2;++ta){
 if(!bmms1253::Eligible(1,M,N,1536,cores)||!bmms1253::AlignedPitch(M,N,1536,ta,false))continue;
 ++active;auto p=bmms1253::MakePlan(1,M,N,1536,cores);
 assert(p.pM==p.mTiles&&p.tasks==cores&&p.blocks==cores&&p.pM*p.pN==cores);
 if(cores==20){assert(M==1280&&p.pM==5&&p.pN==4);++active20;}
 std::vector<int> seen(p.pN*M,0);long long cells=0;
 for(int task=0;task<p.tasks;++task){int ms=task/p.pN,ns=task%p.pN;
  int mb=ms*256,me=std::min(mb+256,M),nb=(ns*p.nTiles/p.pN)*128,ne=std::min(((ns+1)*p.nTiles/p.pN)*128,N);
  assert(mb<me&&nb<ne);cells+=1LL*(me-mb)*(ne-nb);
  for(int sub=0;sub<2;++sub){int vr=(me-mb)/2;
   for(int i=0;i<vr;++i)++seen[ns*M+mb+sub*vr+i];
  }
 }
 assert(cells==1LL*M*N);for(int x:seen){assert(x==1);++partials;}
}
assert(active20==64);
printf("{\"active_metadata_plans\":%d,\"active20\":%d,\"partial_element_writes\":%lld}\n",active,active20,partials);
}
'''
(OUT/'host_r53.cpp').write_text(code)
subprocess.run(['g++','-O2','-std=c++17',str(OUT/'host_r53.cpp'),'-o',str(OUT/'host_r53.exe')],check=True)
host=json.loads(subprocess.check_output([str(OUT/'host_r53.exe')],text=True))
checks=0
for ar in range(16,257,16):
 for br in [64,128]:
  for ta in [False,True]:
   aa=[];bb=[];kr1=256
   for kk in range(0,256,64):
    for i in range(ar//16):
     off=i*kr1*16+kk*16 if ta else (kk//16)*ar*16+i*256
     aa.extend(off//256+q*(1 if ta else ar//16) for q in range(4))
    for j in range(4):bb.extend((kk+j*16)//16+q*(kr1//16) for q in range(br//16))
   assert sorted(aa)==list(range(ar*256//256))
   assert sorted(bb)==list(range(br*256//256));checks+=1
  for sub in [0,1]:
   vr=ar//2
   for row in range(vr):
    src=sub*vr*128+row*128
    assert src+br<=32768
    # 128 columns -> one pairwise Max and one 64-wide reduction per row.
    read=[row*128+i for i in range(64)]+[row*128+64+i for i in range(64)]
    assert max(read)<vr*128
report=dict(parent_recovered_exactly=True,host=host,NZ_layout_checks=checks,
            L1_bytes=393216,L0A_bytes=65536,L0B_bytes=32768,L0C_bytes=131072,
            explicit_UB_bytes_max=65536+32+2*128*4+3*1520*4,
            macro_prefetch_event_model='same r30 K1=256 model as r51/r52 audit',
            limitation='CPU indexing/ownership model, not physical device race proof')
(OUT/'static_r53.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

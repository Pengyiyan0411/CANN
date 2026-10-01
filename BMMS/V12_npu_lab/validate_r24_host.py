from pathlib import Path
import json,subprocess,hashlib
r=Path(__file__).resolve().parent;o=r.parent/'BMMS_V12';d=r/'host_r24';d.mkdir(exist_ok=True)
old=(o/'v12_r22_dense_nz_pitch.asc').read_text(encoding='utf-8')
new=(o/'v12_r24_probe_r22_complement.asc').read_text(encoding='utf-8')
def section(t,a,b):return t[t.index(a):t.index(b,t.index(a))]
a=section(old,'namespace bmms1222 {','static inline bool TryLaunch')
b=section(new,'namespace bmms1224 {','static inline bmms11r2::Plan StressPlan')
assert a.replace('bmms1222','bmms1224')==b
# Verify the early exits, plan construction, and allocation are identical.
a=section(old,'    if(!Eligible(B,M,N,K,dtype,cores)||!Prefer','    auto ap=ws;')
b=section(new,'    if(!Eligible(B,M,N,K,dtype,cores)||Prefer','    // Diagnostic only:')
assert a.replace('bmms1222','bmms1224').replace('||!Prefer','||Prefer')==b
base=(o/'v12_baseline_r19.asc').read_bytes()
raw=(o/'v12_r24_probe_r22_complement.asc').read_bytes()
a=raw.index(b'\n// BMMS1224_BEGIN');b=raw.index(b'// BMMS1224_END',a)+len(b'// BMMS1224_END\n\n')
stripped=raw[:a]+raw[b:]
hook=b'    if(bmms1224::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
assert stripped.replace(hook,b'',1)==base
t=(r/'host_c1112/host.cpp').read_text(encoding='utf-8').split('void need(bool b)')[0]
t+=section(new,'namespace bmms1224 {','static inline bool TryLaunch')+'}\n'
t+=r'''
void need(bool b){if(!b)throw std::runtime_error("r24 host invariant");}
int main(){
 int checks=0,hits=0;
 for(int B:{1,2})for(int M:{1008,1024,1040,1152,1168,1536,2032,2048})
 for(int N:{2032,2048,2064,3072,3088,8192,8208})
 for(int K:{1504,1536,1568,1632,1760,1792,2048,2176,2208,4064,4096})
 for(int dt:{0,1,2,3})for(int cores:{1,20,64})for(int layout=0;layout<4;++layout){
  bool e=bmms1224::Eligible(B,M,N,K,dt,cores);
  need(e==bmms1222::Eligible(B,M,N,K,dt,cores));
  bool pref=bmms1224::Prefer(M,N,K,layout/2,layout%2);
  need(pref==bmms1222::Prefer(M,N,K,layout/2,layout%2));++checks;
  if(!e)continue;
  auto p=bmms1219::MakePlan(M,N,K,cores,layout/2,layout%2);
  need(bmms1224::ValidPlan(p,cores)==bmms1222::ValidPlan(p,cores));
  if(pref||!bmms1224::ValidPlan(p,cores))continue;
  auto q=bmms1224::StressPlan(p);
  need(q.B==1&&q.M==M&&q.N==N&&q.K==K&&q.pM==1&&q.pN==1&&q.tasks==1&&q.blocks==1);
  need(q.mTiles==p.cube.mTiles&&q.nTiles==p.cube.nTiles);
  uint64_t begin=bmms1219::ABytes(p)+bmms1219::BBytes(p);
  need(begin%32==0&&bmms11r2::RingBytes(q)%32==0);
  need(begin+bmms11r2::WorkspaceBytes(q)<=bmms1219::WorkspaceBytes(p));
  int64_t cells=0;
  // One group covers every output cell exactly once before the reductions.
  for(int mi=0;mi<q.mTiles;++mi)for(int ni=0;ni<q.nTiles;++ni)
    cells+=int64_t(std::min(128,M-mi*128))*std::min(256,N-ni*256);
  need(cells==int64_t(M)*N);++hits;
 }
 std::cout<<"{\"guard_checks\":"<<checks<<",\"stress_plan_checks\":"<<hits<<",\"passed\":true}\n";
}
'''
(d/'host.cpp').write_text(t,encoding='utf-8')
subprocess.run(['C:/msys64/ucrt64/bin/g++.exe','-O2','-std=c++17',str(d/'host.cpp'),'-o',str(d/'host.exe')],check=True)
p=subprocess.run([str(d/'host.exe')],check=True,capture_output=True,text=True)
result=json.loads(p.stdout);result.update(guard_functions_identical=True,only_prefer_negated=True,allocation_text_identical=True,parent_byte_recovery=True,source_sha256=hashlib.sha256(raw).hexdigest())
(d/'RESULTS.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))

"""Discrete ownership check for cross-macro L1 prefetch; not hardware scheduling."""
from pathlib import Path
import json,hashlib
r=Path(__file__).resolve().parents[1];o=r/'BMMS_V12'
raw=(o/'v12_r30_dense_macro_prefetch.asc').read_bytes();base=(o/'v12_baseline_r19.asc').read_bytes()
a=raw.index(b'\n// BMMS1230_BEGIN');b=raw.index(b'// BMMS1230_END',a)+len(b'// BMMS1230_END\n\n')
hook=b'    if(bmms1230::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
assert (raw[:a]+raw[b:]).replace(hook,b'',1)==base
checks=macros=loads=0
for K in range(1536,4096,32):
 for mEnd,nEnd in [(128,256),(256,512),(272,784),(656,1040),(1024,2048),(2032,8192)]:
  ready=[False]*2;free=[False]*2;payload=[None]*2;pref=False;start=0
  # Multiple independent tasks must leave no flags/prefetch behind.
  for task in range(2):
   coords=[(m,n,min(128,mEnd-m),min(256,nEnd-n)) for m in range(0,mEnd,128) for n in range(0,nEnd,256)]
   for ix,coord in enumerate(coords):
    hasNext=ix+1<len(coords);phase=start;kc=(K+255)//256
    def load(s,xy,k):
     global loads
     assert not ready[s] and not free[s]
     payload[s]=(xy,k,min(256,K-k));ready[s]=True;loads+=1
    def waitfree(s):
     assert free[s];free[s]=False
    if not pref:load(phase,coord,0)
    pref=False
    for ki in range(kc):
     s1=(ki&1)^phase;kr=min(256,K-ki*256)
     assert ready[s1] and payload[s1]==(coord,ki*256,kr);ready[s1]=False
     if ki+1<kc:
      nxt=s1^1
      if ki>=1:waitfree(nxt)
      load(nxt,coord,(ki+1)*256)
     elif hasNext:
      nxt=s1^1
      if kc>=2:waitfree(nxt)
      load(nxt,coords[ix+1],0);start=nxt;pref=True
     for kk in range(0,kr,64):
      assert payload[s1]==(coord,ki*256,kr)
     assert not free[s1];free[s1]=True
    if hasNext:
     waitfree(((kc-1)&1)^phase)
     assert sum(ready)==1 and ready[start] and not any(free)
    else:
     for s in range(min(2,kc)):waitfree(s^phase)
     start=0
     assert not any(ready) and not any(free) and not pref
    macros+=1
   checks+=1
result=dict(passed=True,parent_byte_recovery=True,sha256=hashlib.sha256(raw).hexdigest(),chains=checks,macros=macros,loads=loads,
 scope='Discrete event ownership and prefetch-coordinate model; not a replacement for hardware racecheck')
(r/'V12_npu_lab/results/r30_host.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))

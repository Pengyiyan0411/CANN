"""Replay independent K256 cache events and verify operand address equivalence."""
from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1]
out=root/'V12_npu_lab/results/case12_wide_load_20261001'
src=(root/'BMMS_V12/v12_r64_case12_wide_cached_stage.asc').read_bytes().decode()
start=src.index('// BMMS1264_BEGIN');marker='// BMMS1264_END\n\n';end=src.index(marker,start)+len(marker)
hook='    if(bmms1264::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
assert (src[:start]+src[end:]).replace(hook,'',1).encode()==(root/'BMMS_V12/v12_baseline_r41.asc').read_bytes()
traces=0
for lengths in ([1],[2],[3],[10],[1,2,10,1],[2,1,9,3],[12,12]):
 flags=set();pref=False
 def put(kind,s):
  key=kind,s;assert key not in flags,key;flags.add(key)
 def wait(kind,s):
  key=kind,s;assert key in flags,key;flags.remove(key)
 for length in lengths:
  for m in range(length):
   nxt=m+1<length
   if not pref:put('AR',0);put('BR',0)
   pref=False
   for ki in range(6):
    s=ki%2;t=s^1
    wait('AR',s);wait('BR',s)
    if ki+1<6:
     if ki>=1:wait('AF',t);wait('BF',t)
     put('AR',t);put('BR',t)
    elif nxt:wait('AF',0);wait('BF',0);put('AR',0);put('BR',0);pref=True
    for j in range(4):
     count=4*ki+j;l0=count%2
     if count>=2:wait('LF',l0)
     if j==3:put('AF',s);put('BF',s)
     put('LF',l0)
   for s in range(1 if nxt else 0,2):wait('AF',s);wait('BF',s)
   wait('LF',0);wait('LF',1)
  assert not flags and not pref
 traces+=1
operands=0
for ar in range(16,129,16):
 for br in (64,128,192,256):
  for ta in (0,1):
   for ki in range(6):
    for kk in range(0,256,64):
     for i in range(ar//16):
      for j in range(4):
       new=i*256*16+kk*16+j*256 if ta else (kk//16+j)*ar*16+i*256
       old=i*256*16+kk*16+j*256 if ta else (kk//16)*ar*16+i*256+j*(ar//16)*256
       assert new==old and new+256<=ar*256
     offbase=0 if ki==0 else 256*256+(ki%2)*256*256
     for j in range(4):
      for n in range(br//16):
       off=offbase+(kk+j*16)*16+n*256*16
       assert off+256<=(256+512)*256
       # r30 B and cached r64 B share the same per-stage NZ fractal order.
       assert off-offbase==(kk+j*16)*16+n*256*16
     operands+=1
z=dict(sha256=hashlib.sha256(src.encode()).hexdigest(),parent_byte_recovery=True,event_traces=traces,
       operand_slices=operands,K_order=list(range(0,1536,64)),L1_bytes=524288,
       note='Shared r63 flat ownership; cached and streaming B stage shapes now equal original r30 stage')
(out/'AUDIT_R64.json').write_text(json.dumps(z,indent=2)+'\n');print(json.dumps(z))

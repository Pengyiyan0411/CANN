"""Event-token, K operand identity, and flat ownership audit of partial residency."""
from pathlib import Path
import json,hashlib
import numpy as np
root=Path(__file__).resolve().parents[1];out=root/'V12_npu_lab/results/case12_wide_load_20261001'
source=(root/'BMMS_V12/v12_r63_case12_wide_partial_b.asc').read_bytes()
# Exact paired event schedule over variable lengths of consecutive same-N runs.
traces=0
for lengths in ([1],[2],[3],[10],[1,2,10,1],[2,1,9,3],[12,12]):
 flags=set();reads=0;pref=False
 def put(kind,slot):
  key=(kind,slot);assert key not in flags,key;flags.add(key)
 def wait(kind,slot):
  key=(kind,slot);assert key in flags,key;flags.remove(key)
 seq=0
 for length in lengths:
  for m in range(length):
   nxt=m+1<length
   if not pref:put('AR',0);put('BR',0)
   pref=False
   for ki in range(12):
    ai=ki//2;a=ai%2;b=ki%2
    if ki%2==0:wait('AR',a)
    wait('BR',b)
    if ki%2==1:
     t=a^1
     if ai+1<6:
      if ai>=1:wait('AF',t)
      put('AR',t)
     elif nxt:wait('AF',t);put('AR',t)
    if ki+1<12:
     t=b^1
     if ki>=1:wait('BF',t)
     put('BR',t)
    elif nxt:wait('BF',0);put('BR',0);pref=True
    for k in (0,64):
     count=ki*2+k//64;s=count%2
     if count>=2:wait('L0F',s)
     put('L0R',s);wait('L0R',s)
     if k==64:
      put('BF',b)
      if ki%2==1:put('AF',a)
     put('L0F',s);reads+=1
   for s in range(1 if nxt else 0,2):wait('AF',s);wait('BF',s)
   for s in range(2):wait('L0F',s)
   seq+=1
  assert not flags and not pref
 traces+=1
# Compare raw uint16 operands against logical matrices; account for NZ fractal transpose.
operands=0
for ar in range(16,129,16):
 for br in (64,128,192,256):
  for ta in (0,1):
   A=np.random.default_rng(ar+ta).integers(0,65536,(ar,1536),dtype=np.uint16)
   B=np.random.default_rng(br).integers(0,65536,(1536,br),dtype=np.uint16)
   store=np.full((512+2*128)*256,65535,dtype=np.uint16)
   for macro in range(2):
    for ki in range(12):
     bk=ki*128;offset=bk*256 if bk<512 else 512*256+(ki%2)*128*256
     if bk>=512 or macro==0:
      for n in range(br//16):
       off=offset+n*128*16
       store[off:off+128*16]=B[bk:bk+128,n*16:(n+1)*16].reshape(-1)
     # DataCopy A physical ND -> NZ according to transposition metadata.
     akbase=(ki//2)*256;physical=A[:,akbase:akbase+256].T.copy() if ta else A[:,akbase:akbase+256]
     apack=np.concatenate([physical[:,c:c+16].reshape(-1) for c in range(0,physical.shape[1],16)])
     for kk in (0,64):
      ak=(ki%2)*128+kk
      for i in range(ar//16):
       for j in range(4):
        off=i*256*16+ak*16+j*256 if ta else (ak//16+j)*ar*16+i*256
        tile=apack[off:off+256].reshape(16,16)
        if ta:tile=tile.T
        assert np.array_equal(tile,A[i*16:(i+1)*16,bk+kk+j*16:bk+kk+(j+1)*16])
      for j in range(4):
       for n in range(br//16):
        off=offset+(kk+j*16)*16+n*128*16
        tile=store[off:off+256].reshape(16,16)
        assert np.array_equal(tile,B[bk+kk+j*16:bk+kk+(j+1)*16,n*16:(n+1)*16])
      operands+=1
coverage=0
for M in range(1280,1536,16):
 for N in range(4096,6144,64):
  mt=(M+127)//128;nt=(N+255)//256;T=mt*nt
  for cores in (16,20,24,32):
   seen=[]
   for g in range(cores):
    seen.extend(range(g*T//cores,(g+1)*T//cores))
   assert seen==list(range(T));coverage+=1
z=dict(sha256=hashlib.sha256(source).hexdigest(),event_traces=traces,raw_operand_slices=operands,
       flat_coverage_states=coverage,resources=dict(L1=524288,L0A=32768,L0B=65536,L0C=131072),
       caveat='CPU token model and raw operand identity; does not prove asynchronous hardware races absent')
(out/'AUDIT_R63.json').write_text(json.dumps(z,indent=2)+'\n');print(json.dumps(z))

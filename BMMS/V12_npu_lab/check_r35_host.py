from pathlib import Path
import json,hashlib
r=Path(__file__).resolve().parents[1];o=r/'BMMS_V12'
raw=(o/'v12_r35_native_macro256.asc').read_bytes();base=(o/'v12_baseline_r33.asc').read_bytes()
a=raw.index(b'\n// BMMS1235_BEGIN');b=raw.index(b'// BMMS1235_END',a)+len(b'// BMMS1235_END\n\n')
hook=b'        if(bmms1235::TryLaunch(a,b,y,p,x.dtype,ta,tb,stream))return;\n'
assert (raw[:a]+raw[b:]).replace(hook,b'',1)==base
mod=raw[a:b].decode();assert 'return bmms49::Select(p)' in mod
assert 'bmms83::NativeRingBytes(p)+bmms83::NativePartialBytes(p)' in mod
assert 'p.M*4' in mod and 'AscendC::ReduceSum(yy,merged,sumBuf.Get<float>(),p.M)' in mod
chains=macros=elements=0
# All possible M partitions (including nonuniform last tiles) within Select.
for M in range(272,8193,16):
 mt=(M+63)//64
 for pm in range(2,min(mt,64)+1):
  covered=[]
  for task in range(pm):
   begin=task*mt//pm*64;end=min((task+1)*mt//pm*64,M)
   assert begin<end
   seq=0;ready=[False,False];free=[False,False];start=0;pref=False
   for m0 in range(begin,end,256):
    ar=min(256,end-m0);assert ar%16==0 and 16<=ar<=256
    nxt=m0+256<end;phase=start
    if not pref:assert not ready[phase];ready[phase]=True
    assert ready[phase];ready[phase]=False;pref=False
    if nxt:
     ns=phase^1;assert not ready[ns] and not free[ns]
     ready[ns]=True;start=ns;pref=True
    assert not free[phase];free[phase]=True
    assert free[phase];free[phase]=False
    if not nxt:assert not any(ready) and not any(free) and not pref;start=0
    vr=ar//2
    for sub in [0,1]:
     lo=m0+sub*vr;hi=lo+vr
     assert m0<=lo<hi<=m0+ar
     covered.extend(range(lo,hi));elements+=vr
     for N in [48,64]:
      ring_lo=sub*vr*64;ring_hi=(sub*vr+vr-1)*64+N
      assert 0<=ring_lo<ring_hi<=256*64
      assert vr*N*4<=128*64*4 and vr<=255
    macros+=1;seq+=1
   chains+=1
  assert covered==list(range(M))
assert 32768+32+512+2*8192*4<192*1024
result=dict(parent_byte_recovery=True,original_plan=True,original_scope=True,M_shards=chains,macros=macros,covered_rows=elements,sha256=hashlib.sha256(raw).hexdigest(),max_UB_bytes=32768+32+512+2*8192*4,max_L0A_bytes=65536,notes='Discrete index/ownership/capacity model; does not prove hardware race freedom')
(r/'V12_npu_lab/results/r35_host.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

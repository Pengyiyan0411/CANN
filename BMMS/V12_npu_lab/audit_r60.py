from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V12'
out=root/'V12_npu_lab/results/case12_nmajor_20261001'
a=(v/'v12_r59_case12_nmajor_b_resident.asc').read_bytes().decode()
b=(v/'v12_r60_case12_nmajor_k128.asc').read_bytes().decode()
start=b.index('// BMMS1260_BEGIN');end=b.index('// BMMS1260_END',start)+len('// BMMS1260_END\n\n')
module=b[start:end]
hook='    if(bmms1260::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
assert b.replace(module,'',1).replace(hook,'',1).encode()==(v/'v12_baseline_r41.asc').read_bytes()
oldstart=a.index('// BMMS1259_BEGIN');oldend=a.index('// BMMS1259_END',oldstart)+len('// BMMS1259_END\n\n')
assert module.replace('1260','1259').replace('K1=256,K0=128,MACRO_ELEMS','K1=256,K0=64,MACRO_ELEMS')==a[oldstart:oldend]
reads=0
for ar in range(16,129,16):
 for br in range(16,129,16):
  for ta in (0,1):
   for stage in range(6):
    for kk in (0,128):
     for i in range(ar//16):
      off=i*256*16+kk*16 if ta else kk//16*ar*16+i*256
      stride=1 if ta else ar//16
      assert off+7*stride*256+256<=ar*256
      assert i*128*16+8*256<=128*128
     for j in range(8):
      off=(stage*256+kk+j*16)*16
      assert off+(br//16-1)*1536*16+256<=1536*128
      assert j*br*16+(br//16)*256<=128*128
     reads+=1
z=dict(sha256=hashlib.sha256(b.encode()).hexdigest(),parent_byte_recovery=True,
       new_module_only_K0_changed=True,K0=128,K_slices=list(range(0,1536,128)),
       operand_shapes_checked=reads,L0A_bytes=65536,L0B_bytes=65536,L1_bytes=524288,
       scope='CPU address bounds and source diff; inherits r59 unchanged host/row coverage')
(out/'AUDIT_R60.json').write_text(json.dumps(z,indent=2)+'\n');print(json.dumps(z))

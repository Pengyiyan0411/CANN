"""CPU index model for r28. Does not model device events or rounding."""
from pathlib import Path
import hashlib,json
r=Path(__file__).resolve().parents[1];o=r/'BMMS_V12'
s=(o/'v12_r28_dense_square_k128.asc').read_bytes();base=(o/'v12_baseline_r19.asc').read_bytes()
a=s.index(b'\n// BMMS1228_BEGIN');b=s.index(b'// BMMS1228_END',a)+len(b'// BMMS1228_END\n\n')
hook=b'    if(bmms1228::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
assert (s[:a]+s[b:]).replace(hook,b'',1)==base
checks=cells=0
for ar in range(16,129,16):
 for br in range(16,129,16):
  # Half-macro consumers, 128-column pitch, negative padding-sensitive values.
  nd=[[-float(1+(m*257+n*97)%1009) for n in range(br)] for m in range(ar)]
  got=[]
  for sub in range(2):
   for row in range(ar//2):
    idx=sub*(ar//2)+row
    c=nd[idx]+[-float('inf')]*(128-br)
    for n in range(64):c[n]=max(c[n],c[n+64])
    got.append(max(c[:64]))
  assert got==[max(x) for x in nd];checks+=1;cells+=ar*br
# L0 operand address mapping in units of 16x16 tiles.
for ar in range(16,129,16):
 for br in range(16,129,16):
  for kr1 in range(32,513,32):
   for kk in range(0,kr1,128):
    kr0=min(128,kr1-kk)
    for ta in [False,True]:
     written={}
     for i in range(ar//16):
      off=i*(kr1//16)+kk//16 if ta else (kk//16)*(ar//16)+i
      for j in range(kr0//16):
       src=off+j*(1 if ta else ar//16)
       coord=(src//(kr1//16),src%(kr1//16)) if ta else (src%(ar//16),src//(ar//16))
       dst=i*(kr0//16)+j
       assert dst not in written and coord==(i,kk//16+j);written[dst]=coord
     assert len(written)==ar*kr0//256;checks+=1
    for tb in [False,True]:
     written={}
     for j in range(kr0//16):
      off=(kk//16+j)*(br//16) if tb else kk//16+j
      for n in range(br//16):
       src=off+n*(1 if tb else kr1//16)
       coord=(src//(br//16),src%(br//16)) if tb else (src%(kr1//16),src//(kr1//16))
       dst=j*(br//16)+n
       assert dst not in written and coord==(kk//16+j,n);written[dst]=coord
     assert len(written)==br*kr0//256;checks+=1
result=dict(passed=True,parent_byte_recovery=True,sha256=hashlib.sha256(s).hexdigest(),index_checks=checks,consumer_cells=cells,
 scope='Host-only exact address/coverage model, not hardware synchronization or FP precision')
(r/'V12_npu_lab/results/r28_host.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result))

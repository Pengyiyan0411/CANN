from pathlib import Path
import hashlib,json
r=Path(__file__).resolve().parents[1];o=r/'BMMS_V12'
s=(o/'v12_r29_dense_m256_load2d.asc').read_bytes();base=(o/'v12_baseline_r19.asc').read_bytes()
a=s.index(b'\n// BMMS1229_BEGIN');b=s.index(b'// BMMS1229_END',a)+len(b'// BMMS1229_END\n\n')
hook=b'    if(bmms1229::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
assert (s[:a]+s[b:]).replace(hook,b'',1)==base
checks=cells=0
for ar in range(16,257,16):
 for br in range(16,129,16):
  for kr1 in range(32,257,32):
   for kk in range(0,kr1,64):
    kr0=min(64,kr1-kk)
    for ta in [False,True]:
     old={};new={}
     for i in range(ar//16):
      for j in range(kr0//16):
       old[i*(kr0//16)+j]=i*(kr1//16)+kk//16+j if ta else (kk//16+j)*(ar//16)+i
     # Actual loop/repeat/dstGap descriptor, indexed in 512-byte fractals.
     for j in range(kr0//16):
      src=kk//16+j if ta else (kk//16+j)*(ar//16)
      for rep in range(ar//16):
       dst=j+rep*(kr0//16)
       assert dst not in new
       new[dst]=src+rep*(kr1//16 if ta else 1)
     assert new==old;checks+=1
    old={j*(br//16)+n:(kk//16+j)*(br//16)+n for j in range(kr0//16) for n in range(br//16)}
    new={i:(kk//16)*(br//16)+i for i in range((kr0//16)*(br//16))}
    assert new==old and len(new)<=255;checks+=1
  nd=[[-float(1+(m*257+n*97)%1009) for n in range(br)] for m in range(ar)]
  got=[]
  for sub in range(2):
   for row in range(ar//2):
    c=nd[sub*(ar//2)+row]+[-float('inf')]*(128-br)
    for n in range(64):c[n]=max(c[n],c[n+64])
    got.append(max(c[:64]))
  assert got==[max(row) for row in nd];checks+=1;cells+=ar*br
result=dict(passed=True,parent_byte_recovery=True,sha256=hashlib.sha256(s).hexdigest(),index_checks=checks,consumer_cells=cells,
 scope='Exact fractal descriptor comparison against prior operand layout; not a hardware synchronization test')
(r/'V12_npu_lab/results/r29_host.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result))

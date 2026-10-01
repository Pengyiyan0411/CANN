"""Exhaustive macro tails: single NZ->ND store, producer/consumer coverage, max."""
from pathlib import Path
import json,hashlib
r=Path(__file__).resolve().parents[1];o=r/'BMMS_V12';base=(o/'v12_baseline_r19.asc').read_bytes()
checks=0;cells=0
for ar in range(16,129,16):
 for br in range(16,257,16):
  nz=[None]*(ar*br);nd=[None]*(128*256)
  for m in range(ar):
   for n in range(br):nz[(n//16)*ar*16+m*16+n%16]=-float(1+(m*257+n*97)%1009)
  for m in range(ar):
   for n in range(br):nd[m*256+n]=nz[(n//16)*ar*16+m*16+n%16]
  gold=[max(nd[m*256:m*256+br]) for m in range(ar)]
  for version in [25,26]:
   read=set();got=[None]*ar
   for sub in range(2):
    if version==25:
     for mo in range(0,ar,64):
      mr=min(64,ar-mo);vr=mr//2
      for row in range(vr):
       actual=mo+sub*vr+row;acc=[-float('inf')]*128
       for no in range(0,br,128):
        nr=min(128,br-no)
        for col in range(nr):
         off=(mo+sub*vr)*256+no+row*256+col
         assert nd[off] is not None and (actual,no+col) not in read
         read.add((actual,no+col));acc[col]=max(acc[col],nd[off])
       got[actual]=max(acc)
    else:
     vr=ar//2
     for row in range(vr):
      actual=sub*vr+row;c=[-float('inf')]*256
      for col in range(br):
       off=sub*vr*256+row*256+col
       assert nd[off] is not None and (actual,col) not in read
       read.add((actual,col));c[col]=nd[off]
      for col in range(64):c[col]=max(c[col],c[col+128])
      for col in range(64):c[col+64]=max(c[col+64],c[col+192])
      for col in range(64):c[col]=max(c[col],c[col+64])
      got[actual]=max(c[:64])
   assert len(read)==ar*br and got==gold
   checks+=1;cells+=len(read)
reports=[]
for v,name in [(25,'dense_macro_store'),(26,'dense_macro_consumer')]:
 p=o/f'v12_r{v}_{name}.asc';raw=p.read_bytes();ns=f'122{v-20}'
 a=raw.index(f'\n// BMMS{ns}_BEGIN'.encode());b=raw.index(f'// BMMS{ns}_END'.encode(),a)+len(f'// BMMS{ns}_END\n\n')
 hook=f'    if(bmms{ns}::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'.encode()
 assert (raw[:a]+raw[b:]).replace(hook,b'',1)==base
 assert b'f.nSize=br;f.mSize=ar;f.srcStride=ar;' in raw[a:b] and b'f.dstStride=BN;' in raw[a:b]
 if v==26:
  for token in [b'+sub*vr*BN;',b'uint32_t((BN-br)*4),uint32_t((BN-br)/8)',b'rp{1,1,1,32,32,32}',b'WholeReduceMax(rows,c,64,vr,1,1,32']:
   assert token in raw[a:b]
 else:
  assert b'+(mo+sub*vr)*BN+no;' in raw[a:b] and b'uint32_t((BN-nr)*4),uint32_t((TN-nr)/8)' in raw[a:b]
 reports.append(dict(version=v,sha256=hashlib.sha256(raw).hexdigest(),parent_byte_recovery=True,
  L1_bytes=393216,L0A_bytes=32768,L0B_bytes=65536,L0C_bytes=131072,
  application_UB_max_bytes=(65536+32+256+256+2032*12) if v==26 else None))
result=dict(passed=True,tail_layout_checks=checks,live_cells_checked=cells,
 scope='Index/reduction model and source contract; not device precision/synchronization simulation',versions=reports)
p=r/'V12_npu_lab/results/dense_macro_host.json';p.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))

"""Resident A address/capacity and B credit model; no hardware timing claims."""
from pathlib import Path
import hashlib,json
r=Path(__file__).resolve().parents[1];o=r/'BMMS_V12'
raw=(o/'v12_r34_shortk_a_resident.asc').read_bytes();base=(o/'v12_baseline_r33.asc').read_bytes()
a=raw.index(b'\n// BMMS1234_BEGIN');b=raw.index(b'// BMMS1234_END',a)+len(b'// BMMS1234_END\n\n')
hook=b'    if(bmms1234::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
assert (raw[:a]+raw[b:]).replace(hook,b'',1)==base
blocks=elements=0
for ar in range(16,129,16):
 for K in range(1024,1536,32):
  assert 128*K*2+2*128*256*2<=512*1024
  for ta in [False,True]:
   for ak in range(0,K,64):
    kr0=min(64,K-ak)
    for i in range(ar//16):
     offset=i*K*16+ak*16 if ta else (ak//16)*ar*16+i*256
     stride=1 if ta else ar//16
     for j in range(kr0//16):
      start=offset+j*stride*256
      assert start>=0 and start+256<=ar*K
      # Check selected logical corners against the independent ND -> NZ formula.
      for mi,ki in [(0,0),(15,0),(0,15),(15,15),(7,9)]:
       m=i*16+mi;k=ak+j*16+ki
       row,col,rows=(k,m,K) if ta else (m,k,ar)
       expected=(col//16)*rows*16+row*16+col%16
       within=ki*16+mi if ta else mi*16+ki
       assert start+within==expected
       elements+=1
      blocks+=1
# Reuse original ownership model with K1=128. Each independent chain is an M row.
code=(r/'V12_npu_lab/check_r30_host.py').read_text()
x=code.index('checks=macros=loads=0');y=code.index('result=dict(',x)
model=code[x:y].replace('range(1536,4096,32)','range(1024,1536,32)')
model=model.replace('[(128,256),(256,512),(272,784),(656,1040),(1024,2048),(2032,8192)]',
                    '[(16,16),(48,512),(64,784),(80,1040),(112,2048),(128,8192)]')
model=model.replace('(K+255)//256','(K+127)//128').replace('min(256,K-', 'min(128,K-').replace('ki*256','ki*128').replace('(ki+1)*256','(ki+1)*128')
scope={};exec(model,scope)
result=dict(parent_byte_recovery=True,address_fractal_blocks=blocks,address_checks=elements,
            row_chains=scope['checks'],macros=scope['macros'],B_loads=scope['loads'],
            sha256=hashlib.sha256(raw).hexdigest(),max_L1=516096,
            scope='Index/capacity/discrete event checks only; no hardware scheduling proof')
(r/'V12_npu_lab/results/r34_host.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))

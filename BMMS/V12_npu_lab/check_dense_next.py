from pathlib import Path
import hashlib,json
r=Path(__file__).resolve().parents[1];o=r/'BMMS_V12';base=(o/'v12_baseline_r30.asc').read_bytes()
records=[]
for v,name in [(31,'dense_compact_load'),(32,'shortk_macro_prefetch')]:
 data=(o/f'v12_r{v}_{name}.asc').read_bytes();a=data.index(f'\n// BMMS12{v}_BEGIN'.encode());b=data.index(f'// BMMS12{v}_END'.encode(),a)+len(f'// BMMS12{v}_END\n\n')
 hook=f'    if(bmms12{v}::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'.encode()
 assert (data[:a]+data[b:]).replace(hook,b'',1)==base
 records.append(dict(version=v,sha256=hashlib.sha256(data).hexdigest(),parent_byte_recovery=True))
checks=0
for ar in range(16,129,16):
 for br in range(16,257,16):
  for kr1 in range(32,257,32):
   for kk in range(0,kr1,64):
    kr0=min(64,kr1-kk)
    for ta in [False,True]:
     for tb in [False,True]:
      olda={};newa={};oldb={};newb={}
      for i in range(ar//16):
       for j in range(kr0//16):
        olda[i*(kr0//16)+j]=((i*(kr1//16)+kk//16+j) if ta else ((kk//16+j)*(ar//16)+i),ta)
      if ta:newa=olda.copy()
      else:
       for j in range(kr0//16):
        for i in range(ar//16):newa[j+i*(kr0//16)]=((kk//16+j)*(ar//16)+i,False)
      for j in range(kr0//16):
       for i in range(br//16):oldb[j*(br//16)+i]=(((kk//16+j)*(br//16)+i) if tb else ((kk//16+j)+i*(kr1//16)),not tb)
      if not tb:newb=oldb.copy()
      else:
       for t in range((kr0//16)*(br//16)):newb[t]=(kk//16*(br//16)+t,False)
      assert olda==newa and oldb==newb
      assert max(newa)<128*64//256 and max(newb)<64*256//256
      checks+=1
assert 65536+32+256+256+8192*12<=192*1024
# Reuse the independent r30 state machine, broadening K to the new route.
code=(r/'V12_npu_lab/check_r30_host.py').read_text(encoding='utf-8')
a=code.index('checks=macros=loads=0');b=code.index('result=dict(',a)
scope={};exec(code[a:b].replace('range(1536,4096,32)','range(1024,1536,32)'),scope)
result=dict(source=records,load2d_fractal_mapping_checks=checks,prefetch_chains=scope['checks'],prefetch_macros=scope['macros'],prefetch_loads=scope['loads'],shortk_max_explicit_ub_bytes=65536+32+256+256+8192*12,scope='Discrete mapping/flag model, not device scheduling proof')
(r/'V12_npu_lab/results/dense_next_host.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))

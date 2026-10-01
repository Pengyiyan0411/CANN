from pathlib import Path
import numpy as np
import json,hashlib
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V12';out=root/'V12_npu_lab/results/case12_bnz_20261001'
s=(v/'v12_r57_case12_b_panel_nz.asc').read_bytes().decode();b=(v/'v12_baseline_r41.asc').read_bytes().decode()
a=s.index('// BMMS1257_BEGIN');e=s.index('// BMMS1257_END',a)+len('// BMMS1257_END\n\n')
hook='    if(bmms1257::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
assert s.replace(s[a:e],'',1).replace(hook,'',1)==b
K=1536;K1=256;BN=256;stages=0
for N in range(4096,6144,64):
 x=np.random.default_rng(N).integers(0,65536,size=(K,N),dtype=np.uint16)
 paddedN=(N+255)//256*256
 packed=np.zeros(K*paddedN,dtype=np.uint16);writes=np.zeros(K*paddedN,dtype=np.uint8)
 for row0 in range(0,K,128):
  for col0 in range(0,N,128):
   rows=128;cols=min(128,N-col0)
   z=x[row0:row0+rows,col0:col0+cols].reshape(rows,cols//16,16).transpose(1,0,2).reshape(-1)
   off=((col0//BN)*(K//K1)+row0//K1)*(K1*BN)+((col0%BN)//16)*K1*16+(row0%K1)*16
   for i in range(cols//16):
    dst=off+i*K1*16;packed[dst:dst+rows*16]=z[i*rows*16:(i+1)*rows*16];writes[dst:dst+rows*16]+=1
 assert np.count_nonzero(writes)==K*N and np.max(writes)==1
 for n0 in range(0,N,BN):
  br=min(BN,N-n0)
  for k0 in range(0,K,K1):
   off=((n0//BN)*(K//K1)+k0//K1)*(K1*BN)
   assert np.all(writes[off:off+br*K1]==1)
   expected=x[k0:k0+K1,n0:n0+br].reshape(K1,br//16,16).transpose(1,0,2).reshape(-1)
   assert np.array_equal(packed[off:off+br*K1],expected);stages+=1
d=dict(version='r57',N_shapes=32,L1_stages_checked=stages,each_live_word_written_once=True,padding_never_loaded=True,
       parent_byte_recovery=True,source_sha256=hashlib.sha256(s.encode()).hexdigest())
(out/'AUDIT_R57.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps(d))

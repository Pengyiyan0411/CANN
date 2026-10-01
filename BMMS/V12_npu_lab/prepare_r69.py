from pathlib import Path
import json,hashlib
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V12';lab=root/'V12_npu_lab/small_20261001'
base=(v/'v12_baseline_r41.asc').read_bytes().decode()
mod=(lab/'r69_device.txt').read_text()+'\n'
for K in range(32,129,8):
 for dt,T in [('f16','half'),('b16','bfloat16_t')]:
  for layout,ta,tb in [('nn','false','false'),('nt','false','true'),('tn','true','false'),('tt','true','true')]:
   mod+=f'__global__ __aicore__ void bmms1269_{dt}_{layout}_{K}(GM_ADDR a,GM_ADDR b,GM_ADDR y,bmms1269::Plan p){{bmms1269::Device<{T},{ta},{tb},{K}>(a,b,y,p);}}\n'
mod+='''namespace bmms1269 {
static inline bool TryLaunch(GM_ADDR a,GM_ADDR b,GM_ADDR y,int B,int M,int N,int K,int dtype,bool ta,bool tb,int cores,aclrtStream stream){
    if(!Eligible(B,M,N,K)||(dtype!=1&&dtype!=2))return false;
    const int workers=B<2*cores?B:2*cores;
    const Plan p{B,M,N,K,int(bmmmaxsum_v43::UseTiny(M,N,K)),workers};
'''
for dt,dti in [('f16',1),('b16',2)]:
 for layout,ta,tb in [('nn','!ta','!tb'),('nt','!ta','tb'),('tn','ta','!tb'),('tt','ta','tb')]:
  mod+=f'    if(dtype=={dti}&&{ta}&&{tb}){{switch(K){{\n'
  for K in range(32,129,8):
   mod+=f'      case {K}:bmms1269_{dt}_{layout}_{K}<<<workers,0,stream>>>(a,b,y,p);return true;\n'
  mod+='    }}\n'
mod+='    return false;\n}\n} // namespace bmms1269\n// BMMS1269_END\n'
hook='    if(bmms1269::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
# Use the ABI's actual transpose parameter names.
abi=base[base.index('extern "C" void run_kernel('):]
print(abi[:500])
assert 'bool ta,bool tb' in abi
pos=base.index('extern "C" void run_kernel(');src=base[:pos]+mod+'\n'+base[pos:]
pos=src.index('    if(bmms1203::TryLaunch');src=src[:pos]+hook+src[pos:]
assert src.replace(mod+'\n','',1).replace(hook,'',1)==base
name='v12_r69_micro_batched_reduce.asc'
for path in (v/name,lab/'r69.asc'):path.write_bytes(src.encode())
(lab/'r69_module.asc').write_bytes(mod.encode());(lab/'r69_hook.txt').write_text(hook)
maxub=(0,None);cases=0
for M in range(2,17):
 for N in range(2,17):
  for K in range(32,129,8):
   if M*N*K>16384:continue
   kp=32 if K<=32 else 64 if K<=64 else 128;NP=(N+7)//8*8;D=M*NP
   ar=(M*K+15)//16*16;br=(N*K+15)//16*16;af=(M*K+7)//8*8;bf=(N*K+7)//8*8
   ub=(ar+br)*2+32+(af+bf)*4+2*kp*4+(M+NP)*kp*4+32+D*kp*4+(2*D+M*8)*4+64
   if ub>maxub[0]:maxub=(ub,[M,N,K])
   # All vector reduction chunks remain 32-byte aligned and <=255 repeats.
   for d in range(0,D,248):assert d%8==0 and min(248,D-d)<=255
   # Gather offsets refer exactly to the logical A[m,k] and B[k,n].
   for ta in (0,1):
    for tb in (0,1):
     for m in range(M):
      for k in range(K):assert (m if ta else m*K)+k*(M if ta else 1)<M*K
     for n in range(N):
      for k in range(K):assert (n*K if tb else n)+k*(1 if tb else N)<N*K
   cases+=1
assert maxub[0]<=192*1024
meta=dict(version='v12_r69',parent='v12_baseline_r41.asc',sha256=hashlib.sha256(src.encode()).hexdigest(),status='pending NPU build/validation',parent_byte_recovery=True,new_device_entries=104,
          valid_MNK_checked=cases,max_UB_bytes=maxub[0],max_UB_shape=maxub[1],eligible='B 1..64, M/N 2..16, K 32..128 step8; original Tiny/Resident only',
          change='Batch-independent workers; batched dot reductions; padded N rows; original Tiny/Resident reduction grouping; explicit final vector sum')
(v/'v12_r69_manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
print(json.dumps(meta,indent=2))

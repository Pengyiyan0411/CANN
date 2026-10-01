from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V12';lab=root/'V12_npu_lab/rethink_20261001'
base=(v/'v12_baseline_r41.asc').read_bytes().decode()
a=base.index('// BMMS1230_BEGIN');end='// BMMS1230_END\n\n';b=base.index(end,a)+len(end)
mod=base[a:b].replace('1230','1267')
def change(old,new):
 global mod
 assert mod.count(old)==1,(old,mod.count(old))
 mod=mod.replace(old,new)
change('return B==1&&M>=1024&&M<2048&&N>=2048&&N<=8192&&K>=1536&&K<4096&&bmms11r2::Eligible(B,M,N,K,cores);',
       'return bmms1230::Eligible(B,M,N,K,cores)&&M>=1280&&M<1536&&N>=4096&&N<6144&&K==1536&&!bmms1241::Eligible(B,M,N,K,cores);')
change('return (!ta||M%64==0)&&((tb?K:N)%64==0);','return !tb&&bmms1230::AlignedPitch(M,N,K,ta,tb);')
change('''            for(int m0=mBegin;m0<mEnd;m0+=AM)for(int n0=nBegin;n0<nEnd;n0+=BN){
                const int nextM=n0+BN<nEnd?m0:m0+AM;
                const int nextN=n0+BN<nEnd?n0+BN:nBegin;''',
'''            const int nCount=nt1-nt0,nShift=ms%nCount;
            for(int m0=mBegin;m0<mEnd;m0+=AM)for(int ni=0;ni<nCount;++ni){
                // Dephase N-block traffic across M shards. Every dot retains its original K order.
                const int n0=nBegin+((ni+nShift)%nCount)*BN;
                const int nextM=ni+1<nCount?m0:m0+AM;
                const int nextN=nBegin+((ni+1+nShift)%nCount)*BN;''')
change('''                for(int nBase=nBegin;nBase<nEnd;nBase+=BN){
                    const int br=MinI(BN,nEnd-nBase),ringSlot=seq&1;''',
'''                const int nCount=nt1-nt0,nShift=ms%nCount;
                for(int ni=0;ni<nCount;++ni){
                    const int nBase=nBegin+((ni+nShift)%nCount)*BN;
                    const int br=MinI(BN,nEnd-nBase),ringSlot=seq&1;''')
for t,typ in [('f16','half'),('b16','bfloat16_t')]:
 for suf,ta in [('nt','false'),('tt','true')]:
  change(f'BMMS1267_KERNEL(bmms1267_{t}_{suf},{typ},{ta},true)\n','')
lo=mod.index('    if(dtype==1){',mod.index('static inline bool TryLaunch'));hi=mod.index('#undef BMMS1267_LAUNCH',lo)
mod=mod[:lo]+'''    if(dtype==1){if(!ta){BMMS1267_LAUNCH(bmms1267_f16_nn);}else{BMMS1267_LAUNCH(bmms1267_f16_tn);}}
    else{if(!ta){BMMS1267_LAUNCH(bmms1267_b16_nn);}else{BMMS1267_LAUNCH(bmms1267_b16_tn);}}
'''+mod[hi:]
hook='    if(bmms1267::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
pos=base.index('extern "C" void run_kernel(');src=base[:pos]+mod+base[pos:]
pos=src.index('    if(bmms1241::TryLaunch');src=src[:pos]+hook+src[pos:]
assert src.replace(mod,'',1).replace(hook,'',1)==base
name='v12_r67_case12_n_order_skew.asc';assert not (v/name).exists()
for path in [v/name,lab/'r67.asc']:path.write_bytes(src.encode())
(lab/'r67_module.asc').write_bytes(mod.encode())
# Verify N coverage and producer look-ahead for every grid admitted by this bounded route.
checks=0
for N in range(4096,6144,64):
 nt=(N+255)//256
 for pn in range(1,nt+1):
  for ns in range(pn):
   n0=ns*nt//pn;n1=(ns+1)*nt//pn;cnt=n1-n0
   assert cnt>0
   for ms in range(12):
    order=[n0+((i+ms%cnt)%cnt) for i in range(cnt)]
    assert sorted(order)==list(range(n0,n1))
    for i in range(cnt):
     next_n=n0+((i+1+ms%cnt)%cnt)
     assert next_n==order[(i+1)%cnt]
    assert sum(min(256,N-n*256) for n in order)==min(N,n1*256)-n0*256
    checks+=1
meta=dict(version='v12_r67',parent='v12_baseline_r41.asc',sha256=hashlib.sha256(src.encode()).hexdigest(),status='pending CANN/NPU verification',parent_byte_recovery=True,new_device_entries=4,change='Rotate N macro traversal by M-shard id; same logical task ownership, K order, buffers and sync; full-K rowmax only',coverage_lookahead_checks=checks,L1=393216,L0A=32768,L0B=65536,L0C=131072)
(v/'v12_r67_manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
(root/'V12_npu_lab/results/rethink_20261001/AUDIT_R67.json').write_text(json.dumps(meta,indent=2)+'\n')
cm=(lab/'CMakeLists.txt').read_text();assert 'foreach(v r41 r65 r66)' in cm
(lab/'CMakeLists.txt').write_text(cm.replace('foreach(v r41 r65 r66)','foreach(v r41 r65 r66 r67)'),newline='\n')
script=(lab/'check_r65.sh').read_text().replace('r65','r67').replace('R65','R67')
(lab/'check_r67.sh').write_text(script,newline='\n')
print(json.dumps(meta))

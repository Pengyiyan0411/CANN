from pathlib import Path
import json,hashlib
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V12';lab=root/'V12_npu_lab/rethink_20261001'
base=(v/'v12_baseline_r41.asc').read_bytes().decode()
a=base.index('// BMMS1230_BEGIN');end='// BMMS1230_END\n\n';b=base.index(end,a)+len(end)
mod=base[a:b].replace('1230','1265')
old='return B==1&&M>=1024&&M<2048&&N>=2048&&N<=8192&&K>=1536&&K<4096&&bmms11r2::Eligible(B,M,N,K,cores);'
mod=mod.replace(old,'return bmms1230::Eligible(B,M,N,K,cores)&&M>=1280&&M<1536&&N>=4096&&N<6144&&K==1536&&!bmms1241::Eligible(B,M,N,K,cores);')
mod=mod.replace('return (!ta||M%64==0)&&((tb?K:N)%64==0);','return !tb&&bmms1230::AlignedPitch(M,N,K,ta,tb);')
mod=mod.replace('l0Free[2],cReady,cFree;','l0Free[2];')
mod=mod.replace('int32_t seq=0;bool cPending=false;','int32_t seq=0;')
line='                if(cPending){AscendC::WaitFlag<AscendC::HardEvent::FIX_M>(cFree);cPending=false;}\n'
assert mod.count(line)==1;mod=mod.replace(line,'')
needle='q.cmatrixInitVal=(l0Count==0);'
assert mod.count(needle)==1
mod=mod.replace(needle,needle+'\n                // Retain L0C ownership across every K slice; publish only the completed full-K tile.\n                q.unitFlag=(ki+1==kCount&&kk+kr0==kr1)?0b11:0b10;')
for line in [
'        AscendC::SetFlag<AscendC::HardEvent::M_FIX>(cReady);\n',
'        AscendC::WaitFlag<AscendC::HardEvent::M_FIX>(cReady);\n',
'        AscendC::SetFlag<AscendC::HardEvent::FIX_M>(cFree);cPending=true;\n',
'        cReady=pipe->AllocEventID<AscendC::HardEvent::M_FIX>();cFree=pipe->AllocEventID<AscendC::HardEvent::FIX_M>();\n',
'        if(cPending)AscendC::WaitFlag<AscendC::HardEvent::FIX_M>(cFree);\n',
'        pipe_->ReleaseEventID<AscendC::HardEvent::M_FIX>(cReady);pipe_->ReleaseEventID<AscendC::HardEvent::FIX_M>(cFree);\n']:
 assert mod.count(line)==1,line;mod=mod.replace(line,'')
mod=mod.replace('f.quantPre=QuantMode_t::NoQuant;','f.quantPre=QuantMode_t::NoQuant;f.unitFlag=0b11;')
assert not any(s in mod for s in ['cPending','cReady','cFree'])
for t,typ in [('f16','half'),('b16','bfloat16_t')]:
 for suf,ta in [('nt','false'),('tt','true')]:mod=mod.replace(f'BMMS1265_KERNEL(bmms1265_{t}_{suf},{typ},{ta},true)\n','')
lo=mod.index('    if(dtype==1){',mod.index('static inline bool TryLaunch'));hi=mod.index('#undef BMMS1265_LAUNCH',lo)
mod=mod[:lo]+'''    if(dtype==1){if(!ta){BMMS1265_LAUNCH(bmms1265_f16_nn);}else{BMMS1265_LAUNCH(bmms1265_f16_tn);}}
    else{if(!ta){BMMS1265_LAUNCH(bmms1265_b16_nn);}else{BMMS1265_LAUNCH(bmms1265_b16_tn);}}
'''+mod[hi:]
hook='    if(bmms1265::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
pos=base.index('extern "C" void run_kernel(');src=base[:pos]+mod+base[pos:]
pos=src.index('    if(bmms1241::TryLaunch');src=src[:pos]+hook+src[pos:]
assert src.replace(mod,'',1).replace(hook,'',1)==base
name='v12_r65_case12_unitflag.asc';assert not (v/name).exists()
for p in [v/name,lab/'r65.asc']:p.write_bytes(src.encode())
(lab/'r65_module.asc').write_bytes(mod.encode())
meta=dict(version='v12_r65',parent='v12_baseline_r41.asc',sha256=hashlib.sha256(src.encode()).hexdigest(),status='pending CANN/NPU verification',parent_byte_recovery=True,new_device_entries=4,change='Only L0C MMAD/FIX ownership via UnitFlag, original K64 order, N256 macro, original pM/pN and consumer/ring',L1=393216,L0A=32768,L0B=65536,L0C=131072)
(v/'v12_r65_manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
(root/'V12_npu_lab/results/rethink_20261001/AUDIT_R65.json').write_text(json.dumps(meta,indent=2)+'\n')
cm=(lab/'CMakeLists.txt').read_text();assert 'foreach(v r41)' in cm
(lab/'CMakeLists.txt').write_text(cm.replace('foreach(v r41)','foreach(v r41 r65)'),newline='\n')
print(json.dumps(meta))

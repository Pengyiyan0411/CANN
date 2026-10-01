"""r63 ablation: aligned K256 A/B stages, cache one B stage, same 512KiB L1."""
from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V12';lab=root/'V12_npu_lab/case12_k1_20261001'
base=(v/'v12_baseline_r41.asc').read_bytes().decode()
mod=(lab/'r63_module.asc').read_bytes().decode().replace('1263','1264')
mod=mod.replace('BK1=128,CACHE_K=512','BK1=256,CACHE_K=256')
mod=mod.replace('(ki%2)*BK1+kk','(ki%(K1/BK1))*BK1+kk')
mod=mod.replace('const int ai=ki/2,as=ai&1,bs=ki&1;','const int ai=ki/(K1/BK1),as=ai&1,bs=ki&1;')
mod=mod.replace('if(ki%2==0)','if(ki%(K1/BK1)==0)')
mod=mod.replace('if(ki%2==1)','if(ki%(K1/BK1)==K1/BK1-1)')
hook='    if(bmms1264::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
pos=base.index('extern "C" void run_kernel(');src=base[:pos]+mod+base[pos:]
pos=src.index('    if(bmms1241::TryLaunch');src=src[:pos]+hook+src[pos:]
assert src.replace(mod,'',1).replace(hook,'',1)==base
name='v12_r64_case12_wide_cached_stage.asc';assert not(v/name).exists()
for p in [v/name,lab/'r64.asc']:p.write_bytes(src.encode())
(lab/'r64_module.asc').write_bytes(mod.encode())
meta=dict(version='v12_r64',parent='v12_baseline_r41.asc',experiment_parent='v12_r63_case12_wide_partial_b.asc',file=name,
          sha256=hashlib.sha256(src.encode()).hexdigest(),status='pending audit and NPU verification',new_device_entries=4,parent_byte_recovery=True,
          change='Same N256 flat runs as r63, B cache K256; A/B both K256 double buffered. Less B reuse but half B staging/events.',
          L1_bytes=524288,L0A_bytes=32768,L0B_bytes=65536,L0C_bytes=131072)
(v/'v12_r64_manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
cm=(lab/'CMakeLists.txt').read_text().replace('r62 r63)','r62 r63 r64)');(lab/'CMakeLists.txt').write_bytes(cm.encode())
script=(lab/'check_r63.sh').read_text().replace('r63','r64').replace('R63','R64')
(lab/'check_r64.sh').write_text(script,encoding='utf-8',newline='\n')
print(json.dumps(meta))

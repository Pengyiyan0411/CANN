"""r59 pipeline correction: BN128 permits K0=128 with BOTH L0 buffers doubled."""
from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V12';lab=root/'V12_npu_lab/case12_k1_20261001'
old=(v/'v12_r59_case12_nmajor_b_resident.asc').read_bytes().decode()
begin=old.index('// BMMS1259_BEGIN');end=old.index('// BMMS1259_END',begin)+len('// BMMS1259_END\n\n')
module=old[begin:end]
assert module.count('K1=256,K0=64,MACRO_ELEMS')==1
changed=module.replace('1259','1260').replace('K1=256,K0=64,MACRO_ELEMS','K1=256,K0=128,MACRO_ELEMS')
src=(old[:begin]+changed+old[end:]).replace('if(bmms1259::TryLaunch','if(bmms1260::TryLaunch')
hook='    if(bmms1260::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
assert src.replace(changed,'',1).replace(hook,'',1).encode()==(v/'v12_baseline_r41.asc').read_bytes()
name='v12_r60_case12_nmajor_k128.asc'
if (v/name).exists():
    previous=(v/name).read_bytes()
    if previous!=src.encode():
        archive=root/'V12_npu_lab/results/case12_nmajor_20261001/r60_generation_error'
        archive.mkdir(exist_ok=True)
        (archive/name).write_bytes(previous)
        (archive/'manifest.json').write_bytes((v/'v12_r60_manifest.json').read_bytes())
(v/name).write_bytes(src.encode());(lab/'r60.asc').write_bytes(src.encode())
meta=dict(version='v12_r60',file=name,parent='v12_baseline_r41.asc',experiment_parent='v12_r59_case12_nmajor_b_resident.asc',
          sha256=hashlib.sha256(src.encode()).hexdigest(),status='pending NPU validation',
          change='Only K0=128 vs r59: half MMAD calls and half A LoadData instructions; preserve L0A/L0B double buffering',
          new_device_entries=4,parent_byte_recovery=True,L1_bytes=524288,L0A_bytes=65536,L0B_bytes=65536,L0C_bytes=131072,
          rounding='K visits in ascending order, but MMAD granularity changes; revalidate against CPU FP64')
(v/'v12_r60_manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
cm=(lab/'CMakeLists.txt').read_text().replace('r58 r59)','r58 r59 r60)')
(lab/'CMakeLists.txt').write_bytes(cm.encode())
script=(lab/'check_r59.sh').read_text().replace('r59','r60').replace('R59','R60')
(lab/'check_r60.sh').write_text(script,encoding='utf-8',newline='\n')
print(json.dumps(meta))

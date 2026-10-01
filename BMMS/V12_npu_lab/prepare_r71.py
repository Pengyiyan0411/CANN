from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V12';lab=root/'V12_npu_lab/small_20261001'
src=(v/'v12_r69_micro_batched_reduce.asc').read_bytes().decode()
old='''    return B>=1&&B<=64&&M>=2&&M<=16&&N>=2&&N<=16&&K>=32&&K<=128&&K%8==0&&
        (bmmmaxsum_v43::UseTiny(M,N,K)||bmms71::UseResident(M,N,K));'''
new='''    // r71 acceptance guard: batched baseline has per-row synchronization;
    // B=1 already uses r03. Avoid adding N padding to its Resident path.
    return B>=1&&B<=64&&M>=2&&M<=16&&N>=2&&N<=16&&K>=32&&K<=128&&K%8==0&&
        (bmmmaxsum_v43::UseTiny(M,N,K)||bmms71::UseResident(M,N,K))&&
        (B>1||N%8==0||bmmmaxsum_v43::UseTiny(M,N,K));'''
assert src.count(old)==1;out=src.replace(old,new)
name='v12_r71_small_cases_guarded.asc';assert not (v/name).exists()
for path in (v/name,lab/'r71.asc'):path.write_bytes(out.encode())
assert out.replace(new,old)==src
meta=dict(version='v12_r71',parent='v12_baseline_r41.asc',derived_from='v12_r69_micro_batched_reduce.asc',sha256=hashlib.sha256(out.encode()).hexdigest(),
          status='pending final validation',change='Guard-only integration; r69 device code identical. B1 Resident with padded N falls back to r41. Dot unchanged.',
          device_identical_to_r69=True,judge15_run=False)
(v/'v12_r71_manifest.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta,indent=2))

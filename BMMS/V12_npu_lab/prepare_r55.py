"""One coverage diagnostic. No new device implementation, exact r54 guards."""
from pathlib import Path
import hashlib, json

root=Path(__file__).resolve().parents[1]; v=root/'BMMS_V12'
lab=root/'V12_npu_lab/case12_k1_20261001'
out=root/'V12_npu_lab/results/r55_coverage_20261001';out.mkdir(exist_ok=True)
base=(v/'v12_baseline_r41.asc').read_bytes().decode()
control=(v/'v12_r54_case12_stride_gated_m256.asc').read_bytes().decode()
a=control.index('namespace bmms1254 {')
b=control.index('template<class T,bool TA,bool TB>',a)
host=control[a:b].replace('1254','1255')
a=control.index('static inline bool TryLaunch(',b)
b=control.index('// BMMS1254_END',a)
launch=control[a:b]
guard_end=launch.index('    const auto p=MakePlan(')
guard=launch[:guard_end]
# Preserve the exact candidate plan and allocation; use its larger workspace.
# Only after successful allocation do we switch to a one-group original r30 plan.
tail=launch[guard_end:]
tail=tail.replace('const auto p=MakePlan(B,M,N,K,cores);','const auto intended=MakePlan(B,M,N,K,cores);')
tail=tail.replace('bmms11r2::WorkspaceBytes(p)','bmms11r2::WorkspaceBytes(intended)',1)
stress='''    auto p=bmms1230::MakePlan(B,M,N,K,cores);
    p.pM=1;p.pN=1;p.tasks=B;p.blocks=1;
    if(bmms11r2::WorkspaceBytes(p)>bmms11r2::WorkspaceBytes(intended))std::abort();
'''
needle='    uint8_t* partial=ws+bmms11r2::RingBytes(p);'
assert tail.count(needle)==1
tail=tail.replace(needle,stress+needle)
tail=tail.replace('bmms1254_f16','bmms1230_f16').replace('bmms1254_b16','bmms1230_b16').replace('1254','1255')
module='// BMMS1255_BEGIN\n// Diagnostic only: exact r54 guard, real single-group r30 computation on HIT.\n'+host+guard+tail+'// BMMS1255_END\n\n'
hook='    if(bmms1255::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
i=base.index('extern "C" void run_kernel(');src=base[:i]+module+base[i:]
i=src.index('    if(bmms1241::TryLaunch');src=src[:i]+hook+src[i:]
assert src.replace(module,'',1).replace(hook,'',1)==base
assert '__global__' not in module and '__aicore__' not in module
assert guard in module
assert 'N%128==64' in host
name='v12_r55_probe_r54_full_gate.asc'
assert not (v/name).exists(), 'Do not overwrite an allocated version'
(v/name).write_bytes(src.encode());(lab/'r55.asc').write_bytes(src.encode())
meta=dict(version='v12_r55',parent='v12_baseline_r41.asc',file=name,sha256=hashlib.sha256(src.encode()).hexdigest(),
    status='pending NPU compilation and calibration; diagnostic only',new_device_entries=0,
    guard_control='v12_r54_case12_stride_gated_m256.asc',parent_byte_recovery=True,
    guard_and_candidate_plan_copied_exactly=True,allocation_size_matches_r54=True,
    mechanism='After the complete r54 guard and allocation, original r30 kernel computes all output on one Cube group. Otherwise exact r41 fallback.',
    npu_report='../V12_npu_lab/results/r55_coverage_20261001/REPORT.md')
(v/'v12_r55_manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
(out/'static_audit.json').write_text(json.dumps(meta,indent=2)+'\n')
cm=(lab/'CMakeLists.txt').read_text().replace('foreach(v r41 r51 r52 r53 r54)','foreach(v r41 r51 r52 r53 r54 r55)')
assert 'foreach(v r41 r51 r52 r53 r54 r55)' in cm
(lab/'CMakeLists.txt').write_bytes(cm.encode())
(lab/'check_r55.sh').write_text('''#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_case12_k1_20261001
trap 'echo R55_FAILED > results/r55.status' ERR
echo R55_BUILD > results/r55.status
cmake -S . -B build >logs/r55_configure.log 2>&1
cmake --build build --target bench_r55 -j2 >logs/r55_build.log 2>&1
echo R55_PRECISION > results/r55.status
timeout 150 ./build/bench_r55 cases/all.txt 3 results/r55_correctness.jsonl >logs/r55_correctness.log 2>&1
echo R55_CALIBRATION > results/r55.status
python3 run_screen.py --baseline r41 --candidate r55 --manifest cases/screen.txt --tag r55_calibration --repeats 12 --discard 3 --windows 2 >logs/r55_calibration.log 2>&1
echo R55_DONE > results/r55.status
''',encoding='utf-8',newline='\n')
print(json.dumps(meta))

"""Single diagnostic: original Case12 domain plus two calibrated N-residue channels."""
from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V12';lab=root/'V12_npu_lab/case12_k1_20261001'
base=(v/'v12_baseline_r41.asc').read_bytes().decode()
old=(v/'v12_r55_probe_r54_full_gate.asc').read_bytes().decode()
a=old.index('static inline bool TryLaunch(',old.index('// BMMS1255_BEGIN'))
b=old.index('// BMMS1255_END',a)
launch=old[a:b].replace('1255','1258')
launch=launch.replace('p.pM=1;p.pN=1;p.tasks=B;p.blocks=1;',
'''// Two real-computation channels: 1 group for aligned128, 2 for offset64.
    const int groups=(N%128==0)?1:2;
    p.pM=groups;p.pN=1;p.tasks=B*groups;p.blocks=groups;''')
mod='''// BMMS1258_BEGIN
// Diagnostic only; 1/2-group true computation encodes N stride inside the original r30 domain.
namespace bmms1258 {
using Plan=bmms1230::Plan;using bmms1230::MakePlan;using bmms1230::AlignedPitch;
static inline bool Eligible(int B,int M,int N,int K,int cores){
    return cores>=2 && bmms1230::Eligible(B,M,N,K,cores) &&
        M>=1280 && M<1536 && N>=4096 && N<6144 && K==1536 &&
        !bmms1241::Eligible(B,M,N,K,cores);
}
'''+launch+'// BMMS1258_END\n\n'
hook='    if(bmms1258::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
i=base.index('extern "C" void run_kernel(');src=base[:i]+mod+base[i:]
i=src.index('    if(bmms1241::TryLaunch');src=src[:i]+hook+src[i:]
assert src.replace(mod,'',1).replace(hook,'',1)==base
assert '__global__' not in mod and '__aicore__' not in mod
name='v12_r58_probe_case12_nstride_channels.asc';assert not (v/name).exists()
(v/name).write_bytes(src.encode());(lab/'r58.asc').write_bytes(src.encode())
meta=dict(version='v12_r58',parent='v12_baseline_r41.asc',file=name,sha256=hashlib.sha256(src.encode()).hexdigest(),
    status='pending NPU precision and channel calibration',diagnostic=True,new_device_entries=0,parent_byte_recovery=True,
    gate='Original r30 route guards with B1 M[1280,1536) N[4096,6144) K1536 TBfalse; does not assume original plan state or new-macro divisibility',
    mechanism='N%128==0 uses1 Cube group; N%128==64 uses2 groups; all arithmetic computed, original r30 kernels, no skipped/reused output',
    allocation='original r30 workspace, stress needs checked at runtime')
(v/'v12_r58_manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
(lab/'check_r58.sh').write_text('''#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_case12_k1_20261001
test "$(cat results/r57.status)" = R57_DONE
trap 'echo R58_FAILED > results/r58.status' ERR
python3 - <<'PY'
from pathlib import Path
p=Path('CMakeLists.txt');s=p.read_text();s=s.replace('foreach(v r41 r51 r52 r53 r54 r55 r56 r57)','foreach(v r41 r51 r52 r53 r54 r55 r56 r57 r58)');p.write_text(s)
PY
echo R58_BUILD > results/r58.status
cmake -S . -B build >logs/r58_configure.log 2>&1
cmake --build build --target bench_r58 -j2 >logs/r58_build.log 2>&1
echo R58_PRECISION > results/r58.status
timeout 180 ./build/bench_r58 cases/all.txt 3 results/r58_correctness.jsonl >logs/r58_correctness.log 2>&1
echo R58_CALIBRATION > results/r58.status
python3 run_screen.py --baseline r41 --candidate r58 --manifest cases/screen.txt --tag r58_calibration --repeats 12 --discard 3 --windows 2 >logs/r58_calibration.log 2>&1
python3 run_screen.py --baseline r41 --candidate r58 --manifest cases/guards.txt --tag r58_fallback --repeats 12 --discard 3 --windows 2 >logs/r58_fallback.log 2>&1
echo R58_DONE > results/r58.status
''',encoding='utf-8',newline='\n')
print(json.dumps(meta))

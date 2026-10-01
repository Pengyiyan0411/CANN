from pathlib import Path
import json,hashlib
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V12';lab=root/'V12_npu_lab/narrow_dense'
base=(v/'v12_baseline_r41.asc').read_bytes().decode();old=(v/'v12_r40_probe_r37_unchanged_in_domain.asc').read_text(encoding='utf-8')
a=old.index('// BMMS1240_BEGIN');b=old.index('// BMMS1240_END',a)+len('// BMMS1240_END');mod=old[a:b].replace('1240','1244')
a=mod.index('static inline bool Matched(');b=mod.index('static inline Plan StressPlan(',a)
mod=mod[:a]+'''static inline bool Matched(int B,int M,int N,int K,int dtype,bool ta,bool tb,int cores){
    // Diagnose only the known wide-N interval; preserve Case11's accepted gain.
    if(!(B==1&&M>=1280&&M<1536&&N>=4096&&N<6144&&K>=1536&&K<1664))return false;
    if((dtype!=1&&dtype!=2)||!bmms1241::Eligible(B,M,N,K,cores)||
       !bmms1241::AlignedPitch(M,N,K,ta,tb))return false;
    const auto family=bmms8::Classify(B,M,N,K,ta,tb);
    return family!=bmms8::Family::Resident&&family!=bmms8::Family::Tiny;
}
'''+mod[b:]
payload=mod+'\n\n';i=base.index('extern "C" void run_kernel(');src=base[:i]+payload+base[i:]
hook='    if(bmms1244::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
i=src.index('    if(bmms1241::TryLaunch');src=src[:i]+hook+src[i:]
assert src.replace(payload,'',1).replace(hook,'',1)==base
name='v12_r44_probe_case12_flat_gate.asc';(v/name).write_bytes(src.encode());(lab/'r44.asc').write_bytes(src.encode())
meta=dict(version='v12_r44',parent='v12_baseline_r41.asc',sha256=hashlib.sha256(src.encode()).hexdigest(),status='diagnostic pending calibration; not a performance version',predicate='Case12 wide-N interval AND exact r41 dtype, eligibility, pitch and family guards',hit_action='one Cube plus two AIVs compute full result via unchanged r30 kernel',new_device_entries=0,parent_byte_recovery=True)
(v/'v12_r44_manifest.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
(lab/'main_r44.asc').write_bytes((lab/'main_r40.asc').read_bytes().replace(b'bmms1240',b'bmms1244').replace(b'r40_hit',b'r44_hit').replace(b'bmms1237::MakePlan',b'bmms1241::MakePlan'))
cm=(lab/'CMakeLists.txt').read_text(encoding='utf-8')
if 'add_executable(bench_r44' not in cm:cm+='''
add_executable(bench_r44 main_r44.asc)
target_compile_definitions(bench_r44 PRIVATE BMMS_KERNEL_HEADER="r44.asc" BMMS_VARIANT="r44")
target_link_libraries(bench_r44 PRIVATE tiling_api register platform unified_dlog dl m graph_base)
target_include_directories(bench_r44 PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_options(bench_r44 PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=dav-2201>)
'''
(lab/'CMakeLists.txt').write_bytes(cm.encode())
script='''#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_narrow_20260929
cmake -S . -B build >logs/r44_configure.log 2>&1
cmake --build build --target bench_r44 -j2 >logs/r44_build.log 2>&1
./build/bench_r44 cases/manifest.txt 3 results/r44_correctness.jsonl >logs/r44_correctness.log 2>&1
./build/bench_r44 cases/extra.txt 3 results/r44_extra_correctness.jsonl >logs/r44_extra_correctness.log 2>&1
./build/bench_r44 cases/r41_holdout.txt 3 results/r44_holdout_correctness.jsonl >logs/r44_holdout_correctness.log 2>&1
python3 - <<'PY'
from pathlib import Path
import json
checks=[json.loads(s) for s in Path('results/r44_holdout_correctness.jsonl').read_text().splitlines()]
hit=[r['case'] for r in checks if r['r44_hit']][:8]
miss=[r['case'] for r in checks if not r['r44_hit'] and r['case']>=232][:8]
ids=set(hit+miss+[200,201,202,203,90,91,93,95,99,101])
rows=[s for name in ['manifest','r41_holdout'] for s in Path(f'cases/{name}.txt').read_text().splitlines() if int(s.split()[0]) in ids]
assert len(rows)==len(ids)
Path('cases/r44_calibration.txt').write_text('\\n'.join(rows)+'\\n')
PY
python3 run_screen.py --baseline r41 --candidate r44 --manifest cases/r44_calibration.txt --tag r44_calibration --repeats 30 --discard 5 --windows 2 >logs/r44_calibration.log 2>&1
python3 archive_r42_r43.py >logs/r42_r43_archive.log
echo R44_DONE
'''
(lab/'check_r44.sh').write_bytes(script.encode());print(json.dumps(meta))

"""Freeze a stride-based selector from screen data, before holdout timing."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1];v=ROOT/'BMMS_V12';lab=ROOT/'V12_npu_lab/case12_k1_20261001'
base=(v/'v12_baseline_r41.asc').read_bytes().decode()
control=(v/'v12_r53_case12_m256_prefetch.asc').read_bytes().decode()
a=control.index('// BMMS1253_BEGIN');b=control.index('// BMMS1253_END',a)+len('// BMMS1253_END\n\n')
mod=control[a:b].replace('1253','1254')
old='!(M>=1280 && M<1536 && N>=4096 && N<6144 && K==1536)'
new='!(M>=1280 && M<1536 && N>=4096 && N<6144 && N%128==64 && K==1536)'
assert mod.count(old)==1;mod=mod.replace(old,new)
hook='    if(bmms1254::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
i=base.index('extern "C" void run_kernel(');src=base[:i]+mod+base[i:]
i=src.index('    if(bmms1241::TryLaunch');src=src[:i]+hook+src[i:]
assert src.replace(mod,'',1).replace(hook,'',1)==base
name='v12_r54_case12_stride_gated_m256.asc'
(v/name).write_bytes(src.encode());(lab/'r54.asc').write_bytes(src.encode())
meta=dict(version='v12_r54',parent='v12_baseline_r41.asc',file=name,sha256=hashlib.sha256(src.encode()).hexdigest(),
          status='selector frozen before holdout; pending validation',change='r53 macro geometry only when N%128==64; all other inputs fall through to frozen r41',
          parent_byte_recovery=True,selector_evidence='r53_screen_summary.json; validate on r53_holdout then independent r54 runs',new_device_entries=4)
(v/'v12_r54_manifest.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta))
cm=(lab/'CMakeLists.txt').read_text().replace('foreach(v r41 r51 r52 r53)','foreach(v r41 r51 r52 r53 r54)')
cm+='''
add_executable(sanitize_r54 main.asc)
target_compile_definitions(sanitize_r54 PRIVATE BMMS_KERNEL_HEADER="r54.asc" BMMS_VARIANT="r54_sanitize")
target_link_libraries(sanitize_r54 PRIVATE tiling_api register platform unified_dlog dl m graph_base)
target_include_directories(sanitize_r54 PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_options(sanitize_r54 PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=dav-2201> $<$<COMPILE_LANGUAGE:ASC>:--cce-enable-sanitizer> $<$<COMPILE_LANGUAGE:ASC>:-gline-tables-only>)
'''
# The sanitizer target is emitted once by this generation step.
assert cm.count('add_executable(sanitize_r54')==1
(lab/'CMakeLists.txt').write_bytes(cm.encode())
(lab/'check_r54.sh').write_text('''#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_case12_k1_20261001
trap 'echo R54_FAILED > results/r54.status' ERR
cmake -S . -B build >logs/r54_configure.log 2>&1
cmake --build build --target bench_r54 -j2 >logs/r54_build.log 2>&1
./build/bench_r54 cases/all.txt 5 results/r54_correctness.jsonl >logs/r54_correctness.log 2>&1
python3 run_screen.py --baseline r41 --candidate r54 --manifest cases/screen.txt --tag r54_screen --repeats 30 --discard 5 --windows 2 >logs/r54_screen.log 2>&1
python3 run_screen.py --baseline r41 --candidate r54 --manifest cases/holdout.txt --tag r54_holdout --repeats 30 --discard 5 --windows 2 >logs/r54_holdout.log 2>&1
echo R54_DONE > results/r54.status
''',encoding='utf-8',newline='\n')

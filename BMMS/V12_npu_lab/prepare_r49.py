from pathlib import Path
import hashlib,json
r=Path(__file__).resolve().parents[1];v=r/'BMMS_V12';lab=r/'V12_npu_lab/narrow_dense'
base=(v/'v12_baseline_r41.asc').read_bytes().decode();old=(v/'v12_r47_case12_fractional_rows.asc').read_text(encoding='utf-8')
a=old.index('// BMMS1247_BEGIN');b=old.index('// BMMS1247_END',a)+len('// BMMS1247_END');mod=old[a:b].replace('1247','1249')
needle='!bmms1241::Eligible(B,M,N,K,cores)'
assert mod.count(needle)==1
mod=mod.replace(needle,needle+'&&bmms1230::MakePlan(B,M,N,K,cores).pN>=4')
payload=mod+'\n\n';i=base.index('extern "C" void run_kernel(');src=base[:i]+payload+base[i:]
hook='    if(bmms1249::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
i=src.index('    if(bmms1241::TryLaunch');src=src[:i]+hook+src[i:]
assert src.replace(payload,'',1).replace(hook,'',1)==base
assert mod.replace('1249','1247').replace('&&bmms1230::MakePlan(B,M,N,K,cores).pN>=4','')==old[a:b]
name='v12_r49_case12_fractional_guarded.asc';(v/name).write_bytes(src.encode());(lab/'r49.asc').write_bytes(src.encode())
meta=dict(version='v12_r49',parent='v12_baseline_r41.asc',sha256=hashlib.sha256(src.encode()).hexdigest(),status='experimental pending independent validation',change='r47 fractional scheduling and sparse row Max, original r30 plan pN>=4 guard',device_equal_to='r47 after namespace normalization',parent_byte_recovery=True,new_device_entries=8,guard_selected_before='r48_holdout performance')
(v/'v12_r49_manifest.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
cm=(lab/'CMakeLists.txt').read_text()
if 'add_executable(bench_r49' not in cm:
    cm+='''
add_executable(bench_r49 main.asc)
target_compile_definitions(bench_r49 PRIVATE BMMS_KERNEL_HEADER="r49.asc" BMMS_VARIANT="r49")
target_link_libraries(bench_r49 PRIVATE tiling_api register platform unified_dlog dl m graph_base)
target_include_directories(bench_r49 PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_options(bench_r49 PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=dav-2201>)
'''
(lab/'CMakeLists.txt').write_bytes(cm.encode())
script='''#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_narrow_20260929
cmake -S . -B build >logs/r49_configure.log 2>&1
cmake --build build --target bench_r49 -j2 >logs/r49_build.log 2>&1
for pair in 'manifest correctness' 'extra extra_correctness' 'r41_holdout holdout_correctness' 'r47_all special_correctness' 'r48_holdout new_correctness'; do
    read -r manifest tag <<< "$pair"
    ./build/bench_r49 cases/$manifest.txt 3 results/r49_$tag.jsonl >logs/r49_$tag.log 2>&1
done
./build/bench_r41 cases/r48_holdout.txt 3 results/r49_new_baseline_correctness.jsonl >logs/r49_new_baseline_correctness.log 2>&1
python3 run_screen.py --baseline r41 --candidate r49 --manifest cases/r48_holdout.txt --tag r49_holdout --repeats 30 --discard 5 --windows 2 >logs/r49_holdout.log 2>&1
echo R49_DONE
'''
(lab/'check_r49.sh').write_bytes(script.encode());print(json.dumps(meta))

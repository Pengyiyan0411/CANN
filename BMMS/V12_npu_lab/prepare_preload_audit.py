from pathlib import Path
root=Path(__file__).resolve().parent/'rethink_20261001'
s=(root/'gemm_main.asc').read_text()
s=s.replace('#include "catlass/gemm/kernel/basic_matmul.hpp"','#include "catlass/gemm/kernel/optimized_matmul.hpp"')
s=s.replace('using DP=Gemm::MmadAtlasA2Pingpong<(AUDIT_UNIT!=0)>;','using DP=Gemm::MmadAtlasA2Preload<true,(AUDIT_SHUFFLE!=0)>;')
s=s.replace('using Kernel=Gemm::Kernel::BasicMatmul<Block,void,Scheduler>;','using Kernel=Gemm::Kernel::OptimizedMatmul<void,void,Block,void,Scheduler>;')
(root/'gemm_preload.asc').write_text(s,newline='\n')
cm=(root/'CMakeLists.txt').read_text()
assert 'gemm_pre0' not in cm
cm+='''
foreach(v pre0 pre1)
 add_executable(gemm_${v} gemm_preload.asc)
 target_compile_definitions(gemm_${v} PRIVATE AUDIT_VARIANT="${v}")
 target_link_libraries(gemm_${v} PRIVATE tiling_api register platform unified_dlog dl m graph_base)
 target_include_directories(gemm_${v} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR} ${CMAKE_CURRENT_SOURCE_DIR}/catlass/include)
 target_compile_options(gemm_${v} PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=dav-2201>)
endforeach()
target_compile_definitions(gemm_pre0 PRIVATE AUDIT_SHUFFLE=0)
target_compile_definitions(gemm_pre1 PRIVATE AUDIT_SHUFFLE=1)
'''
(root/'CMakeLists.txt').write_text(cm,newline='\n')
sc=(root/'run_gemm_audit.py').read_text().replace("['r41','native','cat0','cat1']","['native','pre0','pre1']").replace("['cat1','cat0','native','r41']","['pre1','pre0','native']").replace("tag=f'gemm_","tag=f'preload_").replace('gemm_audit','preload_audit')
(root/'run_preload_audit.py').write_text(sc,newline='\n')
(root/'preload_audit.sh').write_text('''#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_rethink_20261001
trap 'echo PRELOAD_FAILED > results/preload.status' ERR
echo PRELOAD_BUILD > results/preload.status
cmake -S . -B build >logs/preload_config.log 2>&1
for v in pre0 pre1; do
 cmake --build build --target gemm_${v} -j2 >logs/${v}_build.log 2>&1
 timeout -k 15 90 ./build/gemm_${v} cases/gemm_smoke.txt 2 results/${v}_smoke.jsonl >logs/${v}_smoke.log 2>&1
 timeout -k 15 180 ./build/gemm_${v} cases/gemm_scope.txt 2 results/${v}_precision.jsonl >logs/${v}_precision.log 2>&1
done
echo PRELOAD_PROFILE > results/preload.status
python3 run_preload_audit.py >logs/preload_audit.log 2>&1
echo PRELOAD_DONE > results/preload.status
''',newline='\n')

#!/usr/bin/env bash
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

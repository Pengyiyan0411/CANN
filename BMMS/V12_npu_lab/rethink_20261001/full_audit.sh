#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_rethink_20261001
trap 'echo FULL_FAILED > results/full.status' ERR
echo FULL_BUILD > results/full.status
cmake -S . -B build >logs/full_configure.log 2>&1
cmake --build build --target gemm_fullcat1 -j2 >logs/full_build.log 2>&1
echo FULL_SMOKE > results/full.status
timeout -k 15 90 ./build/gemm_fullcat1 cases/gemm_smoke.txt 2 results/fullcat1_smoke.jsonl >logs/fullcat1_smoke.log 2>&1
echo FULL_PRECISION > results/full.status
timeout -k 15 180 ./build/gemm_fullcat1 cases/gemm_scope.txt 2 results/fullcat1_precision.jsonl >logs/fullcat1_precision.log 2>&1
echo FULL_PROFILE > results/full.status
python3 run_full_audit.py >logs/full_audit.log 2>&1
echo FULL_DONE > results/full.status

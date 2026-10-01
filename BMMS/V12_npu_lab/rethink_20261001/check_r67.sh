#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_rethink_20261001
trap 'echo R67_FAILED > results/r67.status' ERR
echo R67_BUILD > results/r67.status
cmake -S . -B build >logs/r67_configure.log 2>&1
cmake --build build --target bench_r67 -j2 >logs/r67_build.log 2>&1
echo R67_SMOKE > results/r67.status
timeout -k 15 90 ./build/bench_r67 cases/gemm_smoke.txt 2 results/r67_smoke.jsonl >logs/r67_smoke.log 2>&1
echo R67_PRECISION > results/r67.status
timeout -k 15 180 ./build/bench_r67 cases/all.txt 3 results/r67_precision.jsonl >logs/r67_precision.log 2>&1
timeout -k 15 180 ./build/bench_r67 /home/developer/bmms_case12_k1_20261001/cases_r59_extra/all.txt 5 results/r67_extra_precision.jsonl >logs/r67_extra_precision.log 2>&1
echo R67_SCREEN > results/r67.status
ln -sf /home/developer/bmms_case12_k1_20261001/build/bench_r41 build/bench_r41
python3 run_screen.py --baseline r41 --candidate r67 --manifest cases/r59_first8.txt --tag r67_first8 --repeats 30 --discard 5 --windows 2 >logs/r67_first8.log 2>&1
echo R67_DONE > results/r67.status

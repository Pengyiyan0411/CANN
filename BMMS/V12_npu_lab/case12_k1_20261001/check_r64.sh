#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_case12_k1_20261001
trap 'echo R64_FAILED > results/r64.status' ERR
echo R64_BUILD > results/r64.status
cmake -S . -B build >logs/r64_configure.log 2>&1
cmake --build build --target bench_r64 -j2 >logs/r64_build.log 2>&1
echo R64_PRECISION > results/r64.status
timeout 180 ./build/bench_r64 cases/all.txt 3 results/r64_correctness.jsonl >logs/r64_correctness.log 2>&1
timeout 180 ./build/bench_r64 cases_r59_extra/all.txt 5 results/r64_extra_precision.jsonl >logs/r64_extra_precision.log 2>&1
echo R64_SCREEN > results/r64.status
python3 run_screen.py --baseline r41 --candidate r64 --manifest cases/r59_first8.txt --tag r64_first8 --repeats 30 --discard 5 --windows 2 >logs/r64_first8.log 2>&1
echo R64_DONE > results/r64.status

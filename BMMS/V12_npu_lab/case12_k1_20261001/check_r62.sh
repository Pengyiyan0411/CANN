#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_case12_k1_20261001
trap 'echo R62_FAILED > results/r62.status' ERR
echo R62_BUILD > results/r62.status
cmake -S . -B build >logs/r62_configure.log 2>&1
cmake --build build --target bench_r62 -j2 >logs/r62_build.log 2>&1
echo R62_PRECISION > results/r62.status
timeout 180 ./build/bench_r62 cases/all.txt 3 results/r62_correctness.jsonl >logs/r62_correctness.log 2>&1
timeout 180 ./build/bench_r62 cases_r59_extra/all.txt 5 results/r62_extra_precision.jsonl >logs/r62_extra_precision.log 2>&1
echo R62_SCREEN > results/r62.status
python3 run_screen.py --baseline r41 --candidate r62 --manifest cases/r59_first8.txt --tag r62_first8 --repeats 30 --discard 5 --windows 2 >logs/r62_first8.log 2>&1
echo R62_DONE > results/r62.status

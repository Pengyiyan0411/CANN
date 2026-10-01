#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_case12_k1_20261001
trap 'echo R63_FAILED > results/r63.status' ERR
echo R63_BUILD > results/r63.status
cmake -S . -B build >logs/r63_configure.log 2>&1
cmake --build build --target bench_r63 -j2 >logs/r63_build.log 2>&1
echo R63_PRECISION > results/r63.status
timeout 180 ./build/bench_r63 cases/all.txt 3 results/r63_correctness.jsonl >logs/r63_correctness.log 2>&1
timeout 180 ./build/bench_r63 cases_r59_extra/all.txt 5 results/r63_extra_precision.jsonl >logs/r63_extra_precision.log 2>&1
echo R63_SCREEN > results/r63.status
python3 run_screen.py --baseline r41 --candidate r63 --manifest cases/r59_first8.txt --tag r63_first8 --repeats 30 --discard 5 --windows 2 >logs/r63_first8.log 2>&1
echo R63_DONE > results/r63.status

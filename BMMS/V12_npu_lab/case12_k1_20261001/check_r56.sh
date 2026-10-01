#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_case12_k1_20261001
trap 'echo R56_FAILED > results/r56.status' ERR
echo R56_BUILD > results/r56.status
cmake -S . -B build >logs/r56_configure.log 2>&1
cmake --build build --target bench_r56 -j2 >logs/r56_build.log 2>&1
echo R56_PRECISION > results/r56.status
timeout 180 ./build/bench_r56 cases/all.txt 3 results/r56_correctness.jsonl >logs/r56_correctness.log 2>&1
echo R56_SCREEN > results/r56.status
python3 run_screen.py --baseline r41 --candidate r56 --manifest cases/screen.txt --tag r56_screen --repeats 30 --discard 5 --windows 2 >logs/r56_screen.log 2>&1
echo R56_DONE > results/r56.status

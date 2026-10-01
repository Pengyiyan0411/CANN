#!/usr/bin/env bash
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

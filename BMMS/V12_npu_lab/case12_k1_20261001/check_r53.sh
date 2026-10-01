#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_case12_k1_20261001
trap 'echo R53_FAILED > results/r53.status' ERR
cmake -S . -B build >logs/r53_configure.log 2>&1
cmake --build build --target bench_r53 -j2 >logs/r53_build.log 2>&1
./build/bench_r53 cases/all.txt 3 results/r53_correctness.jsonl >logs/r53_correctness.log 2>&1
python3 run_screen.py --baseline r41 --candidate r53 --manifest cases/screen.txt --tag r53_screen --repeats 30 --discard 5 --windows 2 >logs/r53_screen.log 2>&1
echo R53_DONE > results/r53.status

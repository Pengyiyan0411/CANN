#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_narrow_20260929
cmake -S . -B build >logs/r46_configure.log 2>&1
cmake --build build --target bench_r46 -j2 >logs/r46_build.log 2>&1
./build/bench_r46 cases/manifest.txt 3 results/r46_correctness.jsonl >logs/r46_correctness.log 2>&1
./build/bench_r46 cases/extra.txt 3 results/r46_extra_correctness.jsonl >logs/r46_extra_correctness.log 2>&1
./build/bench_r46 cases/r41_holdout.txt 3 results/r46_holdout_correctness.jsonl >logs/r46_holdout_correctness.log 2>&1
python3 run_screen.py --baseline r41 --candidate r46 --manifest cases/r42_screen.txt --tag r46_screen --repeats 30 --discard 5 --windows 2 >logs/r46_screen.log 2>&1
echo R46_DONE

#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_narrow_20260929
cmake -S . -B build >logs/r41_configure.log 2>&1
cmake --build build --target bench_r41 -j2 >logs/r41_build.log 2>&1
./build/bench_r41 cases/manifest.txt 3 results/r41_correctness.jsonl >logs/r41_correctness.log 2>&1
./build/bench_r41 cases/extra.txt 3 results/r41_extra_correctness.jsonl >logs/r41_extra_correctness.log 2>&1
./build/bench_r41 cases/r41_holdout.txt 3 results/r41_holdout_correctness.jsonl >logs/r41_holdout_correctness.log 2>&1
python3 run_screen.py --baseline r33 --candidate r41 --manifest cases/holdout.txt --tag r41_discovery --repeats 30 --discard 5 --windows 2 >logs/r41_discovery.log 2>&1
python3 run_screen.py --baseline r33 --candidate r41 --manifest cases/r41_holdout.txt --tag r41_holdout --repeats 30 --discard 5 --windows 2 >logs/r41_holdout.log 2>&1
echo R41_DONE

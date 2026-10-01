#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_narrow_20260929
cmake -S . -B build >logs/r42_configure.log 2>&1
cmake --build build --target bench_r42 -j2 >logs/r42_build.log 2>&1
./build/bench_r42 cases/manifest.txt 3 results/r42_correctness.jsonl >logs/r42_correctness.log 2>&1
./build/bench_r42 cases/extra.txt 3 results/r42_extra_correctness.jsonl >logs/r42_extra_correctness.log 2>&1
./build/bench_r42 cases/r41_holdout.txt 3 results/r42_holdout_correctness.jsonl >logs/r42_holdout_correctness.log 2>&1
awk '$3 >= 1280 && $3 < 1536 && $4 >= 4096 && $4 < 6144 && $5 >= 1536 && $5 < 1664' cases/r41_holdout.txt >cases/r42_screen.txt
python3 run_screen.py --baseline r41 --candidate r42 --manifest cases/r42_screen.txt --tag r42_screen --repeats 30 --discard 5 --windows 2 >logs/r42_screen.log 2>&1
echo R42_DONE

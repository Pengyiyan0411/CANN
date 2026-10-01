#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_narrow_20260929
cmake -S . -B build >logs/r45_configure.log 2>&1
cmake --build build --target bench_r45 -j2 >logs/r45_build.log 2>&1
./build/bench_r45 cases/manifest.txt 3 results/r45_correctness.jsonl >logs/r45_correctness.log 2>&1
./build/bench_r45 cases/extra.txt 3 results/r45_extra_correctness.jsonl >logs/r45_extra_correctness.log 2>&1
./build/bench_r45 cases/r41_holdout.txt 3 results/r45_holdout_correctness.jsonl >logs/r45_holdout_correctness.log 2>&1
python3 run_screen.py --baseline r41 --candidate r45 --manifest cases/r42_screen.txt --tag r45_screen --repeats 30 --discard 5 --windows 2 >logs/r45_screen.log 2>&1
echo R45_DONE

#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_narrow_20260929
TORCH_DEVICE_BACKEND_AUTOLOAD=0 python3 generate_r47.py >logs/r47_generate.log 2>&1
cmake -S . -B build >logs/r47_configure.log 2>&1
cmake --build build --target bench_r47 -j2 >logs/r47_build.log 2>&1
./build/bench_r47 cases/manifest.txt 3 results/r47_correctness.jsonl >logs/r47_correctness.log 2>&1
./build/bench_r47 cases/extra.txt 3 results/r47_extra_correctness.jsonl >logs/r47_extra_correctness.log 2>&1
./build/bench_r47 cases/r41_holdout.txt 3 results/r47_holdout_correctness.jsonl >logs/r47_holdout_correctness.log 2>&1
./build/bench_r41 cases/r47_all.txt 3 results/r47_new_baseline_correctness.jsonl >logs/r47_new_baseline_correctness.log 2>&1
./build/bench_r47 cases/r47_all.txt 3 results/r47_new_correctness.jsonl >logs/r47_new_correctness.log 2>&1
python3 run_screen.py --baseline r41 --candidate r47 --manifest cases/r42_screen.txt --tag r47_screen --repeats 30 --discard 5 --windows 2 >logs/r47_screen.log 2>&1
python3 run_screen.py --baseline r41 --candidate r47 --manifest cases/r47_holdout.txt --tag r47_holdout --repeats 30 --discard 5 --windows 2 >logs/r47_holdout.log 2>&1
echo R47_DONE

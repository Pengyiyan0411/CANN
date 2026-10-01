#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_narrow_20260929
TORCH_DEVICE_BACKEND_AUTOLOAD=0 python3 generate_r43.py >logs/r43_generate.log 2>&1
cmake -S . -B build >logs/r43_configure.log 2>&1
cmake --build build --target bench_r43 -j2 >logs/r43_build.log 2>&1
./build/bench_r43 cases/manifest.txt 3 results/r43_correctness.jsonl >logs/r43_correctness.log 2>&1
./build/bench_r43 cases/extra.txt 3 results/r43_extra_correctness.jsonl >logs/r43_extra_correctness.log 2>&1
./build/bench_r43 cases/r41_holdout.txt 3 results/r43_holdout_correctness.jsonl >logs/r43_holdout_correctness.log 2>&1
./build/bench_r43 cases/r43_all.txt 3 results/r43_c8_correctness.jsonl >logs/r43_c8_correctness.log 2>&1
python3 run_screen.py --baseline r41 --candidate r43 --manifest cases/r43_screen.txt --tag r43_screen --repeats 30 --discard 5 --windows 2 >logs/r43_screen.log 2>&1
echo R43_SCREEN_DONE

#!/usr/bin/env bash
set -eo pipefail
cd /home/developer/bmms_v12_lab_20260928
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cmake -S . -B build >logs/c12_r20_configure.log 2>&1
cmake --build build --target c12_r20_build -j3 >logs/c12_r20_build.log 2>&1
python3 generate_c12_holdout.py >results/c12_holdout_generate.log 2>&1
./build/bench_r20 cases_c12_screen/manifest.txt 3 results/c12_r20_screen_correctness.jsonl >results/c12_r20_screen_correctness.log 2>&1
./build/bench_r19 cases_c12_holdout/manifest.txt 3 results/c12_r19_holdout_correctness.jsonl >results/c12_r19_holdout_correctness.log 2>&1
./build/bench_r20 cases_c12_holdout/manifest.txt 3 results/c12_r20_holdout_correctness.jsonl >results/c12_r20_holdout_correctness.log 2>&1
./build/event_bench_r20 cases_c12_holdout/screen.txt 10 results/c12_r20_holdout_event.jsonl >results/c12_r20_holdout_event.log 2>&1
./build/event_bench_r20 cases_c12_holdout/screen.txt 10 results/c12_r20_holdout_event_repeat.jsonl >results/c12_r20_holdout_event_repeat.log 2>&1
BMMS_EVENT_AA=1 ./build/event_bench_r20 cases_c12_screen/profile.txt 6 results/c12_r20_aa.jsonl >results/c12_r20_aa.log 2>&1
echo C12_R20_DONE

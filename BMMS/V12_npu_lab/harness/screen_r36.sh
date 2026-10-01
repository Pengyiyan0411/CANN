#!/usr/bin/env bash
set -eo pipefail
cd /home/developer/bmms_v12_lab_20260928
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cmake -S . -B build >logs/r36_configure.log 2>&1
cmake --build build --target r36_build -j2 >logs/r36_build.log 2>&1
echo BUILD_DONE
./build/bench_r36 cases_native/manifest.txt 3 results/r36_native_correctness.jsonl >results/r36_native_correctness.log 2>&1
./build/bench_r36 cases_native_holdout/manifest.txt 3 results/r36_holdout_correctness.jsonl >results/r36_holdout_correctness.log 2>&1
echo PRECISION_DONE
./build/event_bench_r36 cases_native/screen.txt 8 results/r36_screen_event.jsonl >results/r36_screen_event.log 2>&1
./build/event_bench_r36 cases_native_holdout/screen.txt 8 results/r36_holdout_event.jsonl >results/r36_holdout_event.log 2>&1
echo SCREEN_DONE

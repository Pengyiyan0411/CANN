#!/usr/bin/env bash
set -eo pipefail
cd /home/developer/bmms_v12_lab_20260928
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cmake -S . -B build >logs/r34_configure.log 2>&1
cmake --build build --target r34_build -j2 >logs/r34_build.log 2>&1
echo BUILD_DONE
./build/bench_r34 cases_shortk/manifest.txt 3 results/r34_screen_correctness.jsonl >results/r34_screen_correctness.log 2>&1
echo PRECISION_DONE
./build/event_bench_r34 cases_shortk/screen.txt 6 results/r34_screen_event.jsonl >results/r34_screen_event.log 2>&1
echo SCREEN_DONE

#!/usr/bin/env bash
set -eo pipefail
cd /home/developer/bmms_v12_lab_20260928
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cmake -S . -B build >logs/dense_next_configure.log 2>&1
cmake --build build --target r31_build r32_build -j2 >logs/dense_next_build.log 2>&1
echo BUILDS_DONE
python3 generate_shortk.py >results/shortk_generation.log 2>&1
echo SHORTK_DATA_DONE
./build/bench_r31 cases_c1112_screen/manifest.txt 3 results/r31_screen_correctness.jsonl >results/r31_screen_correctness.log 2>&1
./build/bench_r31 cases_r25_values/manifest.txt 3 results/r31_values_correctness.jsonl >results/r31_values_correctness.log 2>&1
./build/event_bench_r31 cases_c1112_screen/aligned.txt 6 results/r31_screen_event.jsonl >results/r31_screen_event.log 2>&1
echo R31_SCREEN_DONE
./build/bench_r32 cases_shortk/manifest.txt 3 results/r32_shortk_correctness.jsonl >results/r32_shortk_correctness.log 2>&1
./build/event_bench_r32 cases_shortk/screen.txt 6 results/r32_screen_event.jsonl >results/r32_screen_event.log 2>&1
echo R32_SCREEN_DONE

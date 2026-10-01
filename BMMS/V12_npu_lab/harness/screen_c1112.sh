#!/usr/bin/env bash
set -eo pipefail
cd /home/developer/bmms_v12_lab_20260928
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cmake -S . -B build >logs/c1112_configure.log 2>&1
cmake --build build --target event_c1112_nz -j2 >logs/c1112_build.log 2>&1
python3 generate_c1112_screen.py >results/c1112_generate.log 2>&1
./build/bench_r19 cases_c1112_screen/manifest.txt 3 results/c1112_r19_correctness.jsonl >results/c1112_r19_correctness.log 2>&1
./build/event_c1112_nz cases_c1112_screen/manifest.txt 6 results/c1112_nz_screen.jsonl >results/c1112_nz_screen.log 2>&1
echo C1112_NZ_SCREEN_DONE

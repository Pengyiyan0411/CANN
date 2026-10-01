#!/usr/bin/env bash
set -eo pipefail
cd /home/developer/bmms_v12_lab_20260928
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cmake -S . -B build >logs/r26_configure.log 2>&1
cmake --build build --target r26_build -j2 >logs/r26_build.log 2>&1
echo R26_BUILD_DONE
for pair in 'screen cases_c1112_screen' 'values cases_r25_values'; do
 read -r label dir <<< "$pair"
 ./build/bench_r26 "$dir/manifest.txt" 3 "results/r26_${label}_correctness.jsonl" >"results/r26_${label}_correctness.log" 2>&1
done
./build/event_bench_r26 cases_c1112_screen/aligned.txt 6 results/r26_screen_event.jsonl >results/r26_screen_event.log 2>&1
echo R26_SCREEN_DONE

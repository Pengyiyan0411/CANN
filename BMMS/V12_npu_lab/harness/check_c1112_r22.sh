#!/usr/bin/env bash
set -eo pipefail
cd /home/developer/bmms_v12_lab_20260928
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cmake -S . -B build >logs/c1112_r22_configure.log 2>&1
cmake --build build --target c1112_r22_build -j3 >logs/c1112_r22_build.log 2>&1
python3 generate_c1112_holdout.py >results/c1112_holdout_generate.log 2>&1
for pair in 'screen cases_c1112_screen' 'holdout cases_c1112_holdout' 'original cases' 'c8 cases_c8_final' 'split cases_split' 'controls cases_split_controls'; do
 read -r label dir <<< "$pair"
 ./build/bench_r22 "$dir/manifest.txt" 3 "results/c1112_r22_${label}_correctness.jsonl" >"results/c1112_r22_${label}_correctness.log" 2>&1
done
./build/event_bench_r22 cases_c1112_screen/screen.txt 8 results/c1112_r22_screen_event.jsonl >results/c1112_r22_screen_event.log 2>&1
./build/event_bench_r22 cases_c1112_holdout/screen.txt 8 results/c1112_r22_holdout_event.jsonl >results/c1112_r22_holdout_event.log 2>&1
./build/event_bench_r22 cases_c1112_holdout/screen.txt 8 results/c1112_r22_holdout_event_repeat.jsonl >results/c1112_r22_holdout_event_repeat.log 2>&1
python3 analyze_c1112.py >results/c1112_r22_event_analysis.log
echo C1112_R22_CHECK_DONE

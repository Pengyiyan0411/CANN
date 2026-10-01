#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
cd /home/developer/bmms_v12_lab_20260928
head -n 64 cases_split/manifest.txt >cases_split/all_screen_layouts.txt
sed -n '20p;36p' cases_split/manifest.txt >cases_split/sanitize_final.txt
for round in 1 2; do
  ./build/event_bench_r12 cases_split/all_screen_layouts.txt 12 results/split_r12_event_alllayouts${round}.jsonl >results/split_r12_event_alllayouts${round}.log 2>&1
done
./build/event_bench_r12 cases_split/holdout.txt 20 results/split_r12_event_holdout_repeat.jsonl >results/split_r12_event_holdout_repeat.log 2>&1
TORCH_DEVICE_BACKEND_AUTOLOAD=0 python3 generate_split_controls.py >logs/split_controls_generate.log 2>&1
./build/bench_r03 cases_split_controls/manifest.txt 3 results/split_r03_controls10.jsonl >results/split_r03_controls10.log 2>&1
./build/bench_r12 cases_split_controls/manifest.txt 3 results/split_r12_controls10.jsonl >results/split_r12_controls10.log 2>&1
python3 run_screen.py --candidate r12 --manifest cases_split_controls/manifest.txt --tag split_r12_routes --windows 2 --repeats 40 --discard 10 >results/split_r12_routes.log 2>&1
timeout 180 mssanitizer -t memcheck --log-file=results/split_r12_memcheck.log -- ./build/bench_r12 cases_split/sanitize_final.txt 1 results/split_r12_memcheck.jsonl >results/split_r12_memcheck_launcher.log 2>&1
timeout 180 mssanitizer -t racecheck --log-file=results/split_r12_racecheck.log -- ./build/bench_r12 cases_split/sanitize_final.txt 1 results/split_r12_racecheck.jsonl >results/split_r12_racecheck_launcher.log 2>&1
python3 analyze_split.py >results/split_final_analysis.log
python3 collect_split.py

#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
cd /home/developer/bmms_v12_lab_20260928
python3 run_screen.py --candidate r11 --manifest cases_split/screen.txt --tag split_r11_screen --windows 2 --repeats 40 --discard 10 >results/split_r11_screen.log 2>&1
for round in 1 2; do
  ./build/event_bench_r11 cases_split/screen.txt 20 results/split_r11_event_screen${round}.jsonl >results/split_r11_event_screen${round}.log 2>&1
done
BMMS_EVENT_AA=1 ./build/event_bench_r11 cases_split/screen.txt 20 results/split_r11_event_aa.jsonl >results/split_r11_event_aa.log 2>&1
./build/event_bench_r11 cases_split/holdout.txt 20 results/split_r11_event_holdout.jsonl >results/split_r11_event_holdout.log 2>&1
./build/event_bench_r11 cases_split/layouts.txt 20 results/split_r11_event_layouts.jsonl >results/split_r11_event_layouts.log 2>&1
python3 run_screen.py --candidate r11 --manifest cases_split/guard.txt --tag split_r11_guard --windows 2 --repeats 40 --discard 10 >results/split_r11_guard.log 2>&1
./build/bench_r11 cases/manifest.txt 3 results/split_r11_legacy34.jsonl >results/split_r11_legacy34.log 2>&1
./build/bench_r11 cases_followup/manifest.txt 3 results/split_r11_legacy66.jsonl >results/split_r11_legacy66.log 2>&1
msprof --output=profiles/split_pipe_r11 --task-time=on --ai-core=on --aic-metrics=PipeUtilization ./build/bench_r11 cases_split/profile.txt 20 results/split_pipe_r11.jsonl >results/split_pipe_r11.log 2>&1
python3 analyze_split.py

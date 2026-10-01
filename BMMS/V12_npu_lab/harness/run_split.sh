#!/usr/bin/env bash
set -euo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
cd /home/developer/bmms_v12_lab_20260928
python3 run_screen.py --candidate r10 --manifest cases_split/screen.txt --tag split_r10_screen --windows 2 --repeats 40 --discard 10 >results/split_r10_screen.log 2>&1
for round in 1 2; do
  ./build/event_bench_r10 cases_split/screen.txt 20 results/split_r10_event_screen${round}.jsonl >results/split_r10_event_screen${round}.log 2>&1
done
BMMS_EVENT_AA=1 ./build/event_bench_r10 cases_split/screen.txt 20 results/split_r10_event_aa.jsonl >results/split_r10_event_aa.log 2>&1
./build/event_bench_r10 cases_split/holdout.txt 20 results/split_r10_event_holdout.jsonl >results/split_r10_event_holdout.log 2>&1
./build/event_bench_r10 cases_split/layouts.txt 20 results/split_r10_event_layouts.jsonl >results/split_r10_event_layouts.log 2>&1
python3 run_screen.py --candidate r10 --manifest cases_split/guard.txt --tag split_r10_guard --windows 2 --repeats 40 --discard 10 >results/split_r10_guard.log 2>&1
./build/bench_r10 cases/manifest.txt 3 results/split_r10_legacy34.jsonl >results/split_r10_legacy34.log 2>&1
./build/bench_r10 cases_followup/manifest.txt 3 results/split_r10_legacy66.jsonl >results/split_r10_legacy66.log 2>&1
msprof --output=profiles/split_pipe_r10 --task-time=on --ai-core=on --aic-metrics=PipeUtilization ./build/bench_r10 cases_split/profile.txt 20 results/split_pipe_r10.jsonl >results/split_pipe_r10.log 2>&1
python3 analyze_split.py

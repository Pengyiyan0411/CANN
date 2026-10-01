#!/usr/bin/env bash
set -euo pipefail
cd /home/developer/bmms_v12_lab_20260928
source /home/developer/Ascend/cann-9.0.0/set_env.sh
./build/bench_r16 cases_c8_holdout/manifest.txt 3 results/c8_r16_holdout_correctness.jsonl >results/c8_r16_holdout_correctness.log 2>&1
./build/bench_r16 cases_split_controls/manifest.txt 3 results/c8_r16_controls_correctness.jsonl >results/c8_r16_controls_correctness.log 2>&1
./build/bench_r16 cases_split/manifest.txt 3 results/c8_r16_split_retention.jsonl >results/c8_r16_split_retention.log 2>&1
./build/event_bench_r16 cases_c8/manifest.txt 12 results/c8_r16_event_repeat.jsonl >results/c8_r16_event_repeat.log 2>&1
./build/event_bench_r16 cases_c8_holdout/screen.txt 12 results/c8_r16_holdout_event.jsonl >results/c8_r16_holdout_event.log 2>&1
BMMS_EVENT_AA=1 ./build/event_bench_r16 cases_c8/screen.txt 8 results/c8_r16_event_aa.jsonl >results/c8_r16_event_aa.log 2>&1
python3 run_screen.py --baseline r12 --candidate r16 --manifest cases_c8/screen.txt --tag c8_r16_task --repeats 40 --discard 10 --windows 2 >results/c8_r16_task.log 2>&1
python3 run_screen.py --baseline r12 --candidate r16 --manifest cases_split_controls/manifest.txt --tag c8_r16_controls --repeats 40 --discard 10 --windows 2 >results/c8_r16_controls.log 2>&1
msprof --output=profiles/c8_pipe_r16 --task-time=on --ai-core=on --aic-metrics=PipeUtilization ./build/bench_r16 cases_c8/smoke.txt 20 results/c8_pipe_r16.jsonl >results/c8_pipe_r16.log 2>&1

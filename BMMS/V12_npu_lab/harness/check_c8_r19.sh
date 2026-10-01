#!/usr/bin/env bash
set -eo pipefail
cd /home/developer/bmms_v12_lab_20260928
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
: >results/c8_r19_sanitizer_status.txt
for check in memcheck racecheck initcheck; do
  set +e
  timeout -k 15 360 mssanitizer -t "$check" --log-file="results/c8_r19_instrumented_${check}.log" -- ./build/sanitize_r19 cases_c8_holdout/sanitize_final.txt 1 "results/c8_r19_instrumented_${check}.jsonl" >"results/c8_r19_instrumented_${check}_launcher.log" 2>&1
  status=$?
  set -e
  echo "$check $status" >>results/c8_r19_sanitizer_status.txt
done
./build/bench_r19 cases_c8/manifest.txt 3 results/c8_r19_correctness.jsonl >results/c8_r19_correctness.log 2>&1
./build/bench_r19 cases_c8_holdout/manifest.txt 3 results/c8_r19_holdout_correctness.jsonl >results/c8_r19_holdout_correctness.log 2>&1
./build/bench_r19 cases_c8_final/manifest.txt 3 results/c8_r19_final_correctness.jsonl >results/c8_r19_final_correctness.log 2>&1
./build/bench_r19 cases_split_controls/manifest.txt 3 results/c8_r19_controls_correctness.jsonl >results/c8_r19_controls_correctness.log 2>&1
./build/bench_r19 cases_split/manifest.txt 3 results/c8_r19_split_retention.jsonl >results/c8_r19_split_retention.log 2>&1
./build/event_bench_r19 cases_c8_final/manifest.txt 12 results/c8_r19_final_event.jsonl >results/c8_r19_final_event.log 2>&1
./build/event_bench_r19 cases_c8_final/manifest.txt 12 results/c8_r19_final_event_repeat.jsonl >results/c8_r19_final_event_repeat.log 2>&1
BMMS_EVENT_AA=1 ./build/event_bench_r19 cases_c8/screen.txt 8 results/c8_r19_event_aa.jsonl >results/c8_r19_event_aa.log 2>&1
python3 run_screen.py --baseline r12 --candidate r19 --manifest cases_c8/screen.txt --tag c8_r19_task --repeats 80 --discard 20 --windows 2 >results/c8_r19_task.log 2>&1
python3 run_screen.py --baseline r12 --candidate r19 --manifest cases_split_controls/c8_unaffected.txt --tag c8_r19_controls_repeat --repeats 80 --discard 20 --windows 4 >results/c8_r19_controls_repeat.log 2>&1
python3 run_screen.py --baseline r12 --candidate r19 --manifest cases_split/screen.txt --tag c8_r19_split_repeat --repeats 80 --discard 20 --windows 4 >results/c8_r19_split_repeat.log 2>&1
python3 archive_c8.py

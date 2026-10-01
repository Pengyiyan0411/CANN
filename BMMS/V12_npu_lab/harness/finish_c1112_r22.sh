#!/usr/bin/env bash
set -eo pipefail
cd /home/developer/bmms_v12_lab_20260928
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
# Execute only after the frozen-policy holdout passes performance review.
./build/bench_r22 cases_c12_holdout/manifest.txt 3 results/c1112_r22_gap_correctness.jsonl >results/c1112_r22_gap_correctness.log 2>&1
python3 select_c1112_profiles.py
for entry in 'public cases_c1112_holdout/public.txt' 'c8_control cases_c8/screen.txt' 'split_control cases_split/screen.txt' 'other_control cases_split_controls/c8_unaffected.txt' 'c910_control cases/c1112_control.txt'; do
 read -r label manifest <<< "$entry"
 python3 run_screen.py --baseline r19 --candidate r22 --manifest "$manifest" --tag "c1112_r22_${label}" --repeats 80 --discard 20 --windows 2 >"results/c1112_r22_${label}.log" 2>&1
done
BMMS_EVENT_AA=1 ./build/event_bench_r22 cases_c1112_holdout/profile.txt 6 results/c1112_r22_holdout_aa_event.jsonl >results/c1112_r22_holdout_aa_event.log 2>&1
: >results/c1112_r22_sanitizer_status.txt
for check in memcheck racecheck; do
 set +e
 timeout -k 15 360 mssanitizer -t "$check" --log-file="results/c1112_r22_instrumented_${check}.log" -- ./build/sanitize_r22 cases_c1112_screen/sanitize.txt 1 "results/c1112_r22_instrumented_${check}.jsonl" >"results/c1112_r22_instrumented_${check}_launcher.log" 2>&1
 status=$?
 set -e
 echo "$check $status" >>results/c1112_r22_sanitizer_status.txt
done
python3 analyze_c1112.py >results/c1112_r22_event_analysis_final.log
echo C1112_R22_FINAL_DONE

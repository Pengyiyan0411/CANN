#!/usr/bin/env bash
set -eo pipefail
cd /home/developer/bmms_v12_lab_20260928
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cmake -S . -B build >logs/c12_r21_configure.log 2>&1
cmake --build build --target c12_r21_build -j3 >logs/c12_r21_build.log 2>&1
for pair in 'screen cases_c12_screen' 'holdout cases_c12_holdout' 'random cases_c12_random' 'original cases' 'c8 cases_c8_final' 'split cases_split' 'controls cases_split_controls'; do
  read -r label dir <<< "$pair"
  ./build/bench_r21 "$dir/manifest.txt" 3 "results/c12_r21_${label}_correctness.jsonl" >"results/c12_r21_${label}_correctness.log" 2>&1
done
./build/event_bench_r21 cases_c12_holdout/screen.txt 10 results/c12_r21_holdout_event.jsonl >results/c12_r21_holdout_event.log 2>&1
./build/event_bench_r21 cases_c12_holdout/screen.txt 10 results/c12_r21_holdout_event_repeat.jsonl >results/c12_r21_holdout_event_repeat.log 2>&1
./build/event_bench_r21 cases_c12_random/manifest.txt 10 results/c12_r21_random_event.jsonl >results/c12_r21_random_event.log 2>&1
./build/event_bench_r21 cases_c12_random/manifest.txt 10 results/c12_r21_random_event_repeat.jsonl >results/c12_r21_random_event_repeat.log 2>&1
BMMS_EVENT_AA=1 ./build/event_bench_r21 cases_c12_screen/profile.txt 6 results/c12_r21_aa.jsonl >results/c12_r21_aa.log 2>&1
python3 analyze_c12_r21.py >results/c12_r21_event_analysis.log
for entry in 'public cases_c12_holdout/screen.txt' 'c8_control cases_c8/screen.txt' 'split_control cases_split/screen.txt' 'other_control cases_split_controls/c8_unaffected.txt'; do
 read -r label manifest <<< "$entry"
 python3 run_screen.py --baseline r19 --candidate r21 --manifest "$manifest" --tag "c12_r21_${label}" --repeats 80 --discard 20 --windows 2 >"results/c12_r21_${label}.log" 2>&1
done
: >results/c12_r21_sanitizer_status.txt
for check in memcheck racecheck; do
 set +e
 timeout -k 15 360 mssanitizer -t "$check" --log-file="results/c12_r21_instrumented_${check}.log" -- ./build/sanitize_r21 cases_c12_holdout/sanitize_packet.txt 1 "results/c12_r21_instrumented_${check}.jsonl" >"results/c12_r21_instrumented_${check}_launcher.log" 2>&1
 status=$?
 set -e
 echo "$check $status" >>results/c12_r21_sanitizer_status.txt
done
python3 review_c12_sanitizers.py
python3 archive_c12.py
echo C12_R21_DONE

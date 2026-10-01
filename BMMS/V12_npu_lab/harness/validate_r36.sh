#!/usr/bin/env bash
set -eo pipefail
cd /home/developer/bmms_v12_lab_20260928
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
version=r36
cmake --build build --target sanitize_r36 -j2 >logs/r36_sanitize_build.log 2>&1
echo SANITIZED_BUILD_DONE
python3 generate_native_final.py >results/r36_generate_final.log 2>&1
echo DATA_DONE
for pair in 'independent cases_native_final' 'shortk cases_shortk' 'longk cases_c1112_holdout' 'original cases' 'c8 cases_c8_final' 'split cases_split' 'controls cases_split_controls'; do
 read -r label dir <<< "$pair"
 ./build/bench_r36 "$dir/manifest.txt" 3 "results/r36_final_${label}_correctness.jsonl" >"results/r36_final_${label}_correctness.log" 2>&1
done
./build/event_bench_r36 cases_native_final/manifest.txt 10 results/r36_final_event.jsonl >results/r36_final_event.log 2>&1
./build/event_bench_r36 cases_native_final/manifest.txt 10 results/r36_repeat_event.jsonl >results/r36_repeat_event.log 2>&1
BMMS_EVENT_AA=1 ./build/event_bench_r36 cases_native_final/screen.txt 8 results/r36_aa_event.jsonl >results/r36_aa_event.log 2>&1
echo PRECISION_EVENTS_DONE
for entry in 'native cases_native_final/public.txt' 'native_boundary cases_native/public.txt' 'shortk cases_shortk/public.txt' 'longk cases_c1112_holdout/dense_public.txt' 'c8 cases_c8/screen.txt' 'split cases_split/screen.txt' 'controls cases_split_controls/c8_unaffected.txt'; do
 read -r label manifest <<< "$entry"
 python3 run_screen.py --baseline r33 --candidate r36 --manifest "$manifest" --tag "r36_${label}_public" --repeats 60 --discard 15 --windows 2 >"results/r36_${label}_public.log" 2>&1
 echo PUBLIC_DONE "$label"
done
: >results/r36_sanitizer_status.txt
for check in memcheck racecheck initcheck; do
 set +e
 timeout -k 15 240 mssanitizer -t "$check" --log-file="results/r36_${check}.log" -- ./build/sanitize_r36 cases_native_final/sanitize.txt 1 "results/r36_${check}.jsonl" >"results/r36_${check}_launcher.log" 2>&1
 status=$?
 set -e
 echo "$check $status" >>results/r36_sanitizer_status.txt
done
echo VALIDATION_DONE

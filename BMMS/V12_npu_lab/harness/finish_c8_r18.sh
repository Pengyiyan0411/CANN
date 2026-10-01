#!/usr/bin/env bash
# Run only after the first sanitizer process AND sanitize_r18 build finish.
set -eo pipefail
cd /home/developer/bmms_v12_lab_20260928
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
grep -Ev '^(5|6) ' cases_split_controls/manifest.txt >cases_split_controls/c8_unaffected.txt
python3 run_screen.py --baseline r12 --candidate r18 --manifest cases_split_controls/c8_unaffected.txt --tag c8_r18_controls_repeat --repeats 80 --discard 20 --windows 4 >results/c8_r18_controls_repeat.log 2>&1
python3 run_screen.py --baseline r12 --candidate r18 --manifest cases_split/screen.txt --tag c8_r18_split_repeat --repeats 80 --discard 20 --windows 4 >results/c8_r18_split_repeat.log 2>&1
: >results/c8_r18_instrumented_status.txt
for check in racecheck initcheck; do
    set +e
    timeout -k 15 360 mssanitizer -t "$check" --log-file="results/c8_r18_instrumented_${check}.log" -- ./build/sanitize_r18 cases_c8_holdout/sanitize_final.txt 1 "results/c8_r18_instrumented_${check}.jsonl" >"results/c8_r18_instrumented_${check}_launcher.log" 2>&1
    status=$?
    set -e
    echo "$check $status" >>results/c8_r18_instrumented_status.txt
done

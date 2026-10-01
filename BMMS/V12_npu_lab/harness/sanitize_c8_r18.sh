#!/usr/bin/env bash
set -eo pipefail
cd /home/developer/bmms_v12_lab_20260928
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
grep -E '^(40|55) ' cases_c8_holdout/manifest.txt >cases_c8_holdout/sanitize_final.txt
: >results/c8_r18_sanitizer_status.txt
for check in memcheck racecheck initcheck; do
    set +e
    timeout 180 mssanitizer -t "$check" --log-file="results/c8_r18_${check}.log" -- ./build/bench_r18 cases_c8_holdout/sanitize_final.txt 1 "results/c8_r18_${check}.jsonl" >"results/c8_r18_${check}_launcher.log" 2>&1
    status=$?
    set -e
    echo "$check $status" >>results/c8_r18_sanitizer_status.txt
done

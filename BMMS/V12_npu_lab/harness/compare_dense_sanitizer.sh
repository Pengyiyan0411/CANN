#!/usr/bin/env bash
set -eo pipefail
cd /home/developer/bmms_v12_lab_20260928
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
: >results/r30_sanitizer_comparison_status.txt
for check in memcheck racecheck initcheck; do
  set +e
  timeout -k 15 240 mssanitizer -t "$check" --log-file="results/r30_baseline_${check}.log" -- ./build/sanitize_r19 cases_r25_values/sanitize.txt 1 "results/r30_baseline_${check}.jsonl" >"results/r30_baseline_${check}_launcher.log" 2>&1
  status=$?
  set -e
  echo "r19 $check $status" >>results/r30_sanitizer_comparison_status.txt
done
set +e
timeout -k 15 240 mssanitizer -t synccheck --log-file=results/r30_synccheck.log -- ./build/sanitize_r30 cases_r25_values/sanitize.txt 1 results/r30_synccheck.jsonl >results/r30_synccheck_launcher.log 2>&1
status=$?
set -e
echo "r30 synccheck $status" >>results/r30_sanitizer_comparison_status.txt
echo SANITIZER_COMPARISON_DONE

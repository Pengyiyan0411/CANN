#!/usr/bin/env bash
set -eo pipefail
cd /home/developer/bmms_v12_lab_20260928
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
# Both are selected packet plans, FP16/BF16, nonzero negative outputs.
sed -n '27,28p' cases_c12_holdout/manifest.txt >cases_c12_holdout/sanitize_packet.txt
: >results/c12_r20_sanitizer_status.txt
for version in r19 r20; do
  for check in memcheck racecheck; do
    set +e
    timeout -k 15 360 mssanitizer -t "$check" --log-file="results/c12_${version}_instrumented_${check}.log" -- ./build/sanitize_${version} cases_c12_holdout/sanitize_packet.txt 1 "results/c12_${version}_instrumented_${check}.jsonl" >"results/c12_${version}_instrumented_${check}_launcher.log" 2>&1
    status=$?
    set -e
    echo "$version $check $status" >>results/c12_r20_sanitizer_status.txt
  done
done
echo C12_SANITIZER_DONE

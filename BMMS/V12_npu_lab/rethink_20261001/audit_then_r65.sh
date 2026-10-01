#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_rethink_20261001
trap 'echo AUDIT_FAILED > results/audit.status' ERR
test "$(cat results/setup.status)" = SETUP_DONE
echo AUDIT_PRECISION > results/audit.status
for v in cat0 cat1 native; do
 timeout -k 15 180 ./build/gemm_${v} cases/gemm_scope.txt 2 results/${v}_precision.jsonl >logs/${v}_precision.log 2>&1
done
echo AUDIT_PROFILE > results/audit.status
python3 run_gemm_audit.py >logs/gemm_audit.log 2>&1
echo AUDIT_DONE > results/audit.status
bash check_r65.sh

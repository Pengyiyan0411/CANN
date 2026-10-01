#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_case12_k1_20261001
chmod 750 san_r54
test -x build/sanitize_r54
set +e
timeout -k 15 180 mssanitizer -t memcheck --block-id=0 --log-file=san_r54/memcheck.log -- ./build/sanitize_r54 cases/r54_memory.txt 1 san_r54/precision.jsonl > logs/r54_memcheck_retry_launcher.log 2>&1
status=$?
set -e
echo "$status" > results/r54_memcheck_retry_status.txt
echo MEMCHECK_FINISHED

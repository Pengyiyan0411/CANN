#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_narrow_20260929
mkdir -p -m 750 san_r41
chmod 750 san_r41
set +e
timeout -k 15 240 mssanitizer -t memcheck --log-file=san_r41/memcheck.log -- ./build/bench_r41 cases/r41_memory.txt 1 san_r41/precision.jsonl >logs/r41_memcheck_retry_launcher.log 2>&1
status=$?
set -e
echo "$status" >san_r41/status.txt
echo R41_MEMCHECK_DONE

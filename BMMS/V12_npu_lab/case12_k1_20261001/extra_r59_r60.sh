#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_case12_k1_20261001
test "$(cat results/r60.status)" = R60_DONE
test -f cases_r59_extra/all.txt
trap 'echo EXTRA_FAILED > results/r59_extra.status' ERR
echo EXTRA_RUNNING > results/r59_extra.status
for v in r41 r59 r60; do
  timeout 180 ./build/bench_$v cases_r59_extra/all.txt 5 results/${v}_extra_precision.jsonl >logs/${v}_extra_precision.log 2>&1
done
echo EXTRA_DONE > results/r59_extra.status

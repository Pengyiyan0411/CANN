#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_narrow_20260929
./build/bench_r37 cases/extra.txt 3 results/r37_extra_correctness.jsonl >logs/r37_extra_correctness.log 2>&1
python3 env.py >logs/environment.log 2>&1
python3 archive.py
echo FINISHED

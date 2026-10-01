#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_narrow_20260929
./build/bench_r41 cases/r50_all.txt 3 results/r50_fresh_baseline_correctness.jsonl >logs/r50_fresh_baseline_correctness.log 2>&1
./build/bench_r50 cases/r50_all.txt 3 results/r50_fresh_correctness.jsonl >logs/r50_fresh_correctness.log 2>&1
python3 run_screen.py --baseline r41 --candidate r50 --manifest cases/r50_holdout.txt --tag r50_holdout --repeats 30 --discard 5 --windows 2 >logs/r50_holdout.log 2>&1
echo R50_HOLDOUT_DONE

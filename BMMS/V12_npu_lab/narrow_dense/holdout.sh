#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_narrow_20260929
./build/event_plans cases/holdout.txt 8 results/r37_holdout.jsonl >logs/r37_holdout.log 2>&1
BMMS_EVENT_AA=1 ./build/event_plans cases/aa.txt 6 results/r37_aa.jsonl >logs/r37_aa.log 2>&1
python3 analyze.py results/r37_screen.jsonl >results/r37_screen_summary.log
python3 analyze.py results/r37_holdout.jsonl >results/r37_holdout_summary.log
python3 analyze.py results/r37_aa.jsonl >results/r37_aa_summary.log
echo HOLDOUT_DONE
cmake --build build --target bench_r33 bench_r37 -j2 >logs/build_public.log 2>&1
./build/bench_r37 cases/manifest.txt 3 results/r37_correctness.jsonl >logs/r37_correctness.log 2>&1
echo PUBLIC_BUILD_DONE

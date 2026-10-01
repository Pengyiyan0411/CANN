#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_narrow_20260929
cmake -S . -B build >logs/plan_sweep_configure.log 2>&1
cmake --build build --target sweep_plans -j2 >logs/plan_sweep_build.log 2>&1
./build/sweep_plans cases/holdout.txt 3 results/plan_sweep.jsonl >logs/plan_sweep.log 2>&1
echo SWEEP_DONE

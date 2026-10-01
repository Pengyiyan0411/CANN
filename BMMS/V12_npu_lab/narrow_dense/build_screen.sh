#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_narrow_20260929
mkdir -p logs results
python3 generate.py >logs/generate.log 2>&1
cmake -S . -B build >logs/configure.log 2>&1
cmake --build build --target event_plans -j2 >logs/build_event.log 2>&1
./build/event_plans cases/screen.txt 8 results/r37_screen.jsonl >logs/r37_screen.log 2>&1
echo SCREEN_DONE

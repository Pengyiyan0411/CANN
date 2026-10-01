#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_narrow_20260929
python3 generate_extra.py >logs/generate_extra.log 2>&1
cmake -S . -B build >logs/merge_configure.log 2>&1
cmake --build build --target event_merge -j2 >logs/build_merge.log 2>&1
./build/event_merge cases/screen.txt 8 results/r38_screen.jsonl >logs/r38_screen.log 2>&1
./build/event_merge cases/holdout.txt 8 results/r38_holdout.jsonl >logs/r38_holdout.log 2>&1
./build/event_merge cases/memory_edge.txt 4 results/r38_memory_edge.jsonl >logs/r38_memory_edge.log 2>&1
python3 analyze.py results/r38_screen.jsonl >results/r38_screen_summary.log
python3 analyze.py results/r38_holdout.jsonl >results/r38_holdout_summary.log
echo MERGE_SCREEN_DONE

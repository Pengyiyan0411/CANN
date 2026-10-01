#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_narrow_20260929
cmake -S . -B build >logs/r49_configure.log 2>&1
cmake --build build --target bench_r49 -j2 >logs/r49_build.log 2>&1
for pair in 'manifest correctness' 'extra extra_correctness' 'r41_holdout holdout_correctness' 'r47_all special_correctness' 'r48_holdout new_correctness'; do
    read -r manifest tag <<< "$pair"
    ./build/bench_r49 cases/$manifest.txt 3 results/r49_$tag.jsonl >logs/r49_$tag.log 2>&1
done
./build/bench_r41 cases/r48_holdout.txt 3 results/r49_new_baseline_correctness.jsonl >logs/r49_new_baseline_correctness.log 2>&1
python3 run_screen.py --baseline r41 --candidate r49 --manifest cases/r48_holdout.txt --tag r49_holdout --repeats 30 --discard 5 --windows 2 >logs/r49_holdout.log 2>&1
echo R49_DONE

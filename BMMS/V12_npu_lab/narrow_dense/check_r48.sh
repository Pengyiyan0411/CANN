#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_narrow_20260929
cmake -S . -B build >logs/r48_configure.log 2>&1
cmake --build build --target bench_r48 -j2 >logs/r48_build.log 2>&1
for pair in 'manifest correctness' 'extra extra_correctness' 'r41_holdout holdout_correctness' 'r47_all new_correctness'; do
    read -r manifest tag <<< "$pair"
    ./build/bench_r48 cases/$manifest.txt 3 results/r48_$tag.jsonl >logs/r48_$tag.log 2>&1
done
python3 run_screen.py --baseline r41 --candidate r48 --manifest cases/r47_holdout.txt --tag r48_screen --repeats 30 --discard 5 --windows 2 >logs/r48_screen.log 2>&1
echo R48_DONE

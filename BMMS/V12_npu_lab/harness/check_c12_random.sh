#!/usr/bin/env bash
set -eo pipefail
cd /home/developer/bmms_v12_lab_20260928
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
python3 generate_c12_random.py >results/c12_random_generate.log 2>&1
./build/bench_r19 cases_c12_random/manifest.txt 3 results/c12_r19_random_correctness.jsonl >results/c12_r19_random_correctness.log 2>&1
./build/bench_r20 cases_c12_random/manifest.txt 3 results/c12_r20_random_correctness.jsonl >results/c12_r20_random_correctness.log 2>&1
./build/event_bench_r20 cases_c12_random/manifest.txt 10 results/c12_r20_random_event.jsonl >results/c12_r20_random_event.log 2>&1
./build/event_bench_r20 cases_c12_random/manifest.txt 10 results/c12_r20_random_event_repeat.jsonl >results/c12_r20_random_event_repeat.log 2>&1
bash regress_c12_r20.sh
echo C12_R20_RANDOM_DONE

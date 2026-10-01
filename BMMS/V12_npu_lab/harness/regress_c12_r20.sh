#!/usr/bin/env bash
set -eo pipefail
cd /home/developer/bmms_v12_lab_20260928
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
./build/bench_r20 cases/manifest.txt 3 results/c12_r20_original_correctness.jsonl >results/c12_r20_original_correctness.log 2>&1
./build/bench_r20 cases_c8_final/manifest.txt 3 results/c12_r20_c8_correctness.jsonl >results/c12_r20_c8_correctness.log 2>&1
./build/bench_r20 cases_split/manifest.txt 3 results/c12_r20_split_correctness.jsonl >results/c12_r20_split_correctness.log 2>&1
./build/bench_r20 cases_split_controls/manifest.txt 3 results/c12_r20_controls_correctness.jsonl >results/c12_r20_controls_correctness.log 2>&1
python3 run_screen.py --baseline r19 --candidate r20 --manifest cases_c12_holdout/screen.txt --tag c12_r20_public --repeats 80 --discard 20 --windows 2 >results/c12_r20_public.log 2>&1
python3 run_screen.py --baseline r19 --candidate r20 --manifest cases_c8/screen.txt --tag c12_r20_c8_control --repeats 80 --discard 20 --windows 2 >results/c12_r20_c8_control.log 2>&1
python3 run_screen.py --baseline r19 --candidate r20 --manifest cases_split/screen.txt --tag c12_r20_split_control --repeats 80 --discard 20 --windows 2 >results/c12_r20_split_control.log 2>&1
python3 run_screen.py --baseline r19 --candidate r20 --manifest cases_split_controls/c8_unaffected.txt --tag c12_r20_other_control --repeats 80 --discard 20 --windows 2 >results/c12_r20_other_control.log 2>&1
echo C12_R20_REGRESS_DONE

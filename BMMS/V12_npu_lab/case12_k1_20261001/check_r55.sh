#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_case12_k1_20261001
trap 'echo R55_FAILED > results/r55.status' ERR
echo R55_BUILD > results/r55.status
cmake -S . -B build >logs/r55_configure.log 2>&1
cmake --build build --target bench_r55 -j2 >logs/r55_build.log 2>&1
echo R55_PRECISION > results/r55.status
timeout 150 ./build/bench_r55 cases/all.txt 3 results/r55_correctness.jsonl >logs/r55_correctness.log 2>&1
echo R55_CALIBRATION > results/r55.status
python3 run_screen.py --baseline r41 --candidate r55 --manifest cases/screen.txt --tag r55_calibration --repeats 12 --discard 3 --windows 2 >logs/r55_calibration.log 2>&1
echo R55_DONE > results/r55.status

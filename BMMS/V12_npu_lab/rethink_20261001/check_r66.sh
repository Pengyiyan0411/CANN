#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_rethink_20261001
trap 'echo R66_FAILED > results/r66.status' ERR
echo R66_BUILD > results/r66.status
cmake -S . -B build >logs/r66_configure.log 2>&1
cmake --build build --target bench_r66 -j2 >logs/r66_build.log 2>&1
echo R66_SMOKE > results/r66.status
timeout -k 15 90 ./build/bench_r66 cases/gemm_smoke.txt 2 results/r66_smoke.jsonl >logs/r66_smoke.log 2>&1
echo R66_PRECISION > results/r66.status
timeout -k 15 180 ./build/bench_r66 cases/all.txt 3 results/r66_precision.jsonl >logs/r66_precision.log 2>&1
timeout -k 15 180 ./build/bench_r66 /home/developer/bmms_case12_k1_20261001/cases_r59_extra/all.txt 5 results/r66_extra_precision.jsonl >logs/r66_extra_precision.log 2>&1
echo R66_SCREEN > results/r66.status
ln -sf /home/developer/bmms_case12_k1_20261001/build/bench_r41 build/bench_r41
python3 run_screen.py --baseline r41 --candidate r66 --manifest cases/r59_first8.txt --tag r66_first8 --repeats 30 --discard 5 --windows 2 >logs/r66_first8.log 2>&1
echo R66_DONE > results/r66.status

#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_rethink_20261001
trap 'echo R65_FAILED > results/r65.status' ERR
echo R65_BUILD > results/r65.status
cmake -S . -B build >logs/r65_configure.log 2>&1
cmake --build build --target bench_r65 -j2 >logs/r65_build.log 2>&1
echo R65_SMOKE > results/r65.status
timeout -k 15 90 ./build/bench_r65 cases/gemm_smoke.txt 2 results/r65_smoke.jsonl >logs/r65_smoke.log 2>&1
echo R65_PRECISION > results/r65.status
timeout -k 15 180 ./build/bench_r65 cases/all.txt 3 results/r65_precision.jsonl >logs/r65_precision.log 2>&1
timeout -k 15 180 ./build/bench_r65 /home/developer/bmms_case12_k1_20261001/cases_r59_extra/all.txt 5 results/r65_extra_precision.jsonl >logs/r65_extra_precision.log 2>&1
echo R65_SCREEN > results/r65.status
ln -sf /home/developer/bmms_case12_k1_20261001/build/bench_r41 build/bench_r41
python3 run_screen.py --baseline r41 --candidate r65 --manifest cases/r59_first8.txt --tag r65_first8 --repeats 30 --discard 5 --windows 2 >logs/r65_first8.log 2>&1
echo R65_DONE > results/r65.status

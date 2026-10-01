#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_case12_k1_20261001
mkdir -p logs results profiles
trap 'echo SETUP_FAILED > results/setup.status' ERR
date -Iseconds > logs/environment.txt
npu-smi info >> logs/environment.txt
python3 -c 'import torch,torch_npu; print(torch.__version__); print(torch.npu.get_device_name(0))' >> logs/environment.txt 2>&1
cmake -S . -B build > logs/configure.log 2>&1
# CPU input preparation overlaps compilation only; no simultaneous NPU workloads.
python3 generate_cases.py > logs/generate.log 2>&1 &
data_pid=$!
cmake --build build --target bench_r41 bench_r51 bench_r52 -j2 > logs/build.log 2>&1
wait "$data_pid"
echo SETUP_DONE > results/setup.status
for v in r41 r51 r52; do
  ./build/bench_$v cases/all.txt 3 results/${v}_correctness.jsonl > logs/${v}_correctness.log 2>&1
done
echo CORRECTNESS_DONE > results/correctness.status
python3 run_screen.py --baseline r41 --candidate r51 --manifest cases/screen.txt --tag r51_screen --repeats 30 --discard 5 --windows 2 > logs/r51_screen.log 2>&1
python3 run_screen.py --baseline r41 --candidate r52 --manifest cases/screen.txt --tag r52_screen --repeats 30 --discard 5 --windows 2 > logs/r52_screen.log 2>&1
echo SCREEN_DONE > results/screen.status

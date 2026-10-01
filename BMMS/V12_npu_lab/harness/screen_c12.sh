#!/usr/bin/env bash
set -eo pipefail
cd /home/developer/bmms_v12_lab_20260928
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cmake -S . -B build >logs/c12_configure.log 2>&1
cmake --build build --target event_c12_plan -j3 >logs/c12_plan_build.log 2>&1
python3 generate_c12_screen.py >results/c12_generate.log 2>&1
./build/bench_r19 cases_c12_screen/manifest.txt 3 results/c12_r19_correctness.jsonl >results/c12_r19_correctness.log 2>&1
C12_PACKET_N=2 ./build/event_c12_plan cases_c12_screen/manifest.txt 6 results/c12_packet2_event.jsonl >results/c12_packet2_event.log 2>&1
C12_PACKET_N=1 ./build/event_c12_plan cases_c12_screen/manifest.txt 6 results/c12_packet1_event.jsonl >results/c12_packet1_event.log 2>&1
echo C12_SCREEN_DONE

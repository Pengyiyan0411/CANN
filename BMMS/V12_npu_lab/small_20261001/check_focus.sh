#!/bin/bash
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_small_20261001
mkdir -p san_focus
chmod 750 san_focus
printf '' > san_focus/status.txt
for check in memcheck racecheck initcheck synccheck; do
  timeout -k 15 180 mssanitizer -t "$check" --log-file="san_focus/${check}.log" -- ./build_san/sanitize_r69 san_cases/focus.txt 1 "san_focus/${check}.jsonl" > "san_focus/${check}_launcher.log" 2>&1
  echo "$check $?" >> san_focus/status.txt
done
for check in memcheck racecheck initcheck; do
  timeout -k 15 120 mssanitizer -t "$check" --block-id=0 --log-file="san_focus/loop_${check}.log" -- ./build_san/sanitize_r69 cases/sanitize_loop.txt 1 "san_focus/loop_${check}.jsonl" > "san_focus/loop_${check}_launcher.log" 2>&1
  echo "loop_$check $?" >> san_focus/status.txt
done
cat san_focus/status.txt

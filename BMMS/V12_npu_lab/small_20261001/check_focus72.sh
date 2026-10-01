#!/bin/bash
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_small_20261001
mkdir -p san_focus72
chmod 750 san_focus72
printf '' > san_focus72/status.txt
for check in memcheck racecheck initcheck synccheck; do
  timeout -k 15 180 mssanitizer -t "$check" --log-file="san_focus72/${check}.log" -- ./build_san72/sanitize_r72 san_cases/focus.txt 1 "san_focus72/${check}.jsonl" > "san_focus72/${check}_launcher.log" 2>&1
  echo "$check $?" >> san_focus72/status.txt
done
for check in memcheck racecheck initcheck; do
  timeout -k 15 120 mssanitizer -t "$check" --block-id=0 --log-file="san_focus72/loop_${check}.log" -- ./build_san72/sanitize_r72 cases/sanitize_loop.txt 1 "san_focus72/loop_${check}.jsonl" > "san_focus72/loop_${check}_launcher.log" 2>&1
  echo "loop_$check $?" >> san_focus72/status.txt
done
cat san_focus72/status.txt

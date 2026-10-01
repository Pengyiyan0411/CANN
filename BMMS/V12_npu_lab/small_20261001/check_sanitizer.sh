#!/bin/bash
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_small_20261001
mkdir -p san_r69
chmod 750 san_r69
printf '' > san_r69/status.txt
for check in memcheck racecheck initcheck synccheck; do
  timeout -k 15 240 mssanitizer -t "$check" --log-file="san_r69/${check}.log" -- ./build_san/sanitize_r69 cases/sanitize_full.txt 1 "san_r69/${check}.jsonl" > "san_r69/${check}_launcher.log" 2>&1
  status=$?
  echo "$check $status" >> san_r69/status.txt
done
cat san_r69/status.txt

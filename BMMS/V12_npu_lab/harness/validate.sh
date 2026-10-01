#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
cd "$(dirname "$0")"
mkdir -p results
for stage in smoke manifest; do
  for version in r03 r06; do
    echo "START ${stage} ${version}"
    timeout 120 "./build/bench_${version}" "cases/${stage}.txt" 3 "results/${version}_${stage}.jsonl" >"results/${version}_${stage}.log" 2>&1 || {
      status=$?
      tail -n 30 "results/${version}_${stage}.log"
      echo "STOP status=${status}; do not launch the next test until device state is checked."
      exit "$status"
    }
    tail -n 3 "results/${version}_${stage}.log"
  done
done

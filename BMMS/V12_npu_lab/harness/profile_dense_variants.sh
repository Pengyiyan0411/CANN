#!/usr/bin/env bash
set -eo pipefail
cd /home/developer/bmms_v12_lab_20260928
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
for v in r28 r29 r30; do
  msprof --output=profiles/dense_pipe_${v}_v1 --task-time=on --ai-core=on --aic-metrics=PipeUtilization ./build/bench_${v} cases_c1112_screen/pipe.txt 30 results/dense_pipe_${v}.jsonl >results/dense_pipe_${v}.log 2>&1
  echo "PIPE_DONE ${v}"
done
echo PROFILE_VARIANTS_DONE

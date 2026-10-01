#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_narrow_20260929
./build/bench_r41 cases/r50_all.txt 3 results/r50_fresh_baseline_correctness.jsonl >logs/r50_fresh_baseline_correctness.log 2>&1
./build/bench_r50 cases/r50_all.txt 3 results/r50_fresh_correctness.jsonl >logs/r50_fresh_correctness.log 2>&1
awk '$1==502 || $1==516' cases/r48_holdout.txt >cases/r49_detail.txt
for metric in PipeUtilization Memory; do
    for version in r41 r49; do
        tag=r49_detail_${metric}_${version}
        msprof --output=profiles/$tag --task-time=on --ai-core=on --aic-metrics=$metric ./build/bench_$version cases/r49_detail.txt 5 results/$tag.jsonl >logs/$tag.log 2>&1
    done
done
echo EPILOGUE_ANALYSIS_DONE

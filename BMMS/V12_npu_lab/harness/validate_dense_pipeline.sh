#!/usr/bin/env bash
# Called with a reviewed version only after screening; all execution is serial.
set -eo pipefail
cd /home/developer/bmms_v12_lab_20260928
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
version="$1"
case "$version" in r30) ;; *) exit 2;; esac
python3 generate_dense_balanced.py >results/dense_balanced_generation.log 2>&1
# Heavy instrumented compilation must finish before event/profiler timings.
cmake --build build --target "${version}_build" "sanitize_${version}" -j2 >"logs/${version}_sanitize_build.log" 2>&1
bash profile_dense_variants.sh >results/profile_dense_variants_job.log 2>&1
for pair in 'screen cases_c1112_screen' 'values cases_r25_values' 'holdout cases_c1112_holdout' 'original cases' 'c8 cases_c8_final' 'split cases_split' 'controls cases_split_controls' 'gap cases_c12_holdout' 'balanced cases_dense_balanced'; do
 read -r label dir <<< "$pair"
 ./build/bench_${version} "$dir/manifest.txt" 3 "results/${version}_${label}_correctness.jsonl" >"results/${version}_${label}_correctness.log" 2>&1
done
./build/event_bench_${version} cases_c1112_screen/aligned.txt 6 "results/${version}_screen_event.jsonl" >"results/${version}_screen_event.log" 2>&1
./build/event_bench_${version} cases_c1112_holdout/aligned.txt 8 "results/${version}_holdout_event.jsonl" >"results/${version}_holdout_event.log" 2>&1
./build/event_bench_${version} cases_c1112_holdout/aligned.txt 8 "results/${version}_holdout_repeat_event.jsonl" >"results/${version}_holdout_repeat_event.log" 2>&1
./build/event_bench_${version} cases_dense_balanced/manifest.txt 10 "results/${version}_balanced_event.jsonl" >"results/${version}_balanced_event.log" 2>&1
python3 - <<'PY'
from pathlib import Path
p=Path('cases_c1112_holdout');ids={0,1,2,3,6,8,9,11,13,17,24,27,34,41,46,54,59,61,63}
lines=[x for x in (p/'manifest.txt').read_text().splitlines() if int(x.split()[0]) in ids]
assert len(lines)==len(ids)
(p/'dense_public.txt').write_text('\n'.join(lines)+'\n')
PY
for entry in 'public cases_c1112_holdout/dense_public.txt' 'c8_control cases_c8/screen.txt' 'split_control cases_split/screen.txt' 'other_control cases_split_controls/c8_unaffected.txt' 'c910_control cases/c1112_control.txt'; do
 read -r label manifest <<< "$entry"
 python3 run_screen.py --baseline r19 --candidate "$version" --manifest "$manifest" --tag "${version}_${label}" --repeats 60 --discard 15 --windows 2 >"results/${version}_${label}.log" 2>&1
done
BMMS_EVENT_AA=1 ./build/event_bench_${version} cases_r25_values/profile.txt 6 "results/${version}_aa_event.jsonl" >"results/${version}_aa_event.log" 2>&1
: >"results/${version}_sanitizer_status.txt"
for check in memcheck racecheck initcheck; do
 set +e
 timeout -k 15 240 mssanitizer -t "$check" --log-file="results/${version}_${check}.log" -- ./build/sanitize_${version} cases_r25_values/sanitize.txt 1 "results/${version}_${check}.jsonl" >"results/${version}_${check}_launcher.log" 2>&1
 status=$?
 set -e
 echo "$check $status" >>"results/${version}_sanitizer_status.txt"
done
true
echo DENSE_VALIDATION_DONE "$version"

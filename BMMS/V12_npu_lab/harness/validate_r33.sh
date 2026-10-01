#!/usr/bin/env bash
set -eo pipefail
cd /home/developer/bmms_v12_lab_20260928
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
version="$1"
case "$version" in r32|r33) ;; *) exit 2;; esac
cmake -S . -B build >logs/r33_configure.log 2>&1
cmake --build build --target "${version}_build" "sanitize_${version}" -j2 >"logs/${version}_sanitize_build.log" 2>&1
echo SANITIZED_BUILD_DONE
python3 generate_shortk_final.py >results/shortk_final_generation.log 2>&1
echo FINAL_DATA_DONE
for pair in 'shortk cases_shortk' 'independent cases_shortk_final' 'longk cases_c1112_holdout' 'values cases_r25_values' 'original cases' 'c8 cases_c8_final' 'split cases_split' 'controls cases_split_controls' 'balanced cases_dense_balanced'; do
 read -r label dir <<< "$pair"
 ./build/bench_${version} "$dir/manifest.txt" 3 "results/${version}_final_${label}_correctness.jsonl" >"results/${version}_final_${label}_correctness.log" 2>&1
done
./build/event_bench_${version} cases_shortk_final/manifest.txt 8 "results/${version}_holdout_event.jsonl" >"results/${version}_holdout_event.log" 2>&1
./build/event_bench_${version} cases_shortk_final/manifest.txt 8 "results/${version}_repeat_event.jsonl" >"results/${version}_repeat_event.log" 2>&1
BMMS_EVENT_AA=1 ./build/event_bench_${version} cases_shortk/screen.txt 6 "results/${version}_aa_event.jsonl" >"results/${version}_aa_event.log" 2>&1
./build/event_bench_${version} cases_shortk/manifest.txt 6 "results/${version}_all80_event.jsonl" >"results/${version}_all80_event.log" 2>&1
echo PRECISION_EVENTS_DONE
for entry in 'shortk_public cases_shortk/public.txt' 'longk_control cases_c1112_holdout/dense_public.txt' 'c8_control cases_c8/screen.txt' 'split_control cases_split/screen.txt' 'other_control cases_split_controls/c8_unaffected.txt'; do
 read -r label manifest <<< "$entry"
 python3 run_screen.py --baseline r30 --candidate "$version" --manifest "$manifest" --tag "${version}_${label}" --repeats 60 --discard 15 --windows 2 >"results/${version}_${label}.log" 2>&1
 echo PUBLIC_DONE "$label"
done
python3 - <<'PY'
from pathlib import Path
p=Path("cases_shortk");ids={64,65,72,73}
(p/"sanitize_final.txt").write_text("".join(x+"\n" for x in (p/"manifest.txt").read_text().splitlines() if int(x.split()[0]) in ids))
PY
: >"results/${version}_sanitizer_status.txt"
for check in memcheck racecheck initcheck; do
 set +e
 timeout -k 15 240 mssanitizer -t "$check" --log-file="results/${version}_${check}.log" -- ./build/sanitize_${version} cases_shortk/sanitize_final.txt 1 "results/${version}_${check}.jsonl" >"results/${version}_${check}_launcher.log" 2>&1
 status=$?
 set -e
 echo "$check $status" >>"results/${version}_sanitizer_status.txt"
done
echo VALIDATION_DONE "$version"

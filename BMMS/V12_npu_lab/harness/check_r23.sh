#!/usr/bin/env bash
set -eo pipefail
cd /home/developer/bmms_v12_lab_20260928
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cmake -S . -B build >logs/r23_configure.log 2>&1
cmake --build build --target bench_r23 -j3 >logs/r23_build.log 2>&1
echo R23_BUILD_DONE
for pair in 'screen cases_c1112_screen' 'holdout cases_c1112_holdout' 'original cases' 'c8 cases_c8_final' 'split cases_split' 'controls cases_split_controls' 'gap cases_c12_holdout'; do
 read -r label dir <<< "$pair"
 ./build/bench_r23 "$dir/manifest.txt" 3 "results/r23_${label}_correctness.jsonl" >"results/r23_${label}_correctness.log" 2>&1
 echo "R23_PRECISION_DONE $label"
done
python3 - <<'PY'
from pathlib import Path
p=Path('cases_c1112_holdout')
ids={0,6,8,13,24,34,41,54}
rows=[r for r in (p/'manifest.txt').read_text().splitlines() if int(r.split()[0]) in ids]
assert len(rows)==len(ids)
(p/'r23_signal.txt').write_text('\n'.join(rows)+'\n')
PY
python3 run_screen.py --baseline r19 --candidate r23 --manifest cases_c1112_holdout/r23_signal.txt --tag r23_signal --repeats 20 --discard 5 --windows 2 >results/r23_signal.log 2>&1
echo R23_SIGNAL_DONE
python3 archive_r23.py
echo R23_ALL_DONE

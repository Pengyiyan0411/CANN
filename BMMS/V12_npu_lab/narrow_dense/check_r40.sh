#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_narrow_20260929
cmake -S . -B build >logs/r40_configure.log 2>&1
cmake --build build --target bench_r40 -j2 >logs/r40_build.log 2>&1
./build/bench_r40 cases/manifest.txt 3 results/r40_correctness.jsonl >logs/r40_correctness.log 2>&1
./build/bench_r40 cases/extra.txt 3 results/r40_extra_correctness.jsonl >logs/r40_extra_correctness.log 2>&1
python3 - <<'PY'
from pathlib import Path
ids={0,5,6,9,12,19,21,22,34,35,46,50,54,58,66,70,74,93,95,99,101}
rows=[s for s in Path('cases/manifest.txt').read_text().splitlines() if int(s.split()[0]) in ids]
assert len(rows)==len(ids)
Path('cases/r40_calibration.txt').write_text('\n'.join(rows)+'\n')
PY
python3 run_screen.py --baseline r33 --candidate r40 --manifest cases/r40_calibration.txt --tag r40_calibration --repeats 30 --discard 5 --windows 2 >logs/r40_calibration.log 2>&1
echo R40_DONE

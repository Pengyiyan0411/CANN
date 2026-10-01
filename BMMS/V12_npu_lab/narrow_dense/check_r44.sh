#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_narrow_20260929
cmake -S . -B build >logs/r44_configure.log 2>&1
cmake --build build --target bench_r44 -j2 >logs/r44_build.log 2>&1
./build/bench_r44 cases/manifest.txt 3 results/r44_correctness.jsonl >logs/r44_correctness.log 2>&1
./build/bench_r44 cases/extra.txt 3 results/r44_extra_correctness.jsonl >logs/r44_extra_correctness.log 2>&1
./build/bench_r44 cases/r41_holdout.txt 3 results/r44_holdout_correctness.jsonl >logs/r44_holdout_correctness.log 2>&1
python3 - <<'PY'
from pathlib import Path
import json
checks=[json.loads(s) for s in Path('results/r44_holdout_correctness.jsonl').read_text().splitlines()]
hit=[r['case'] for r in checks if r['r44_hit']][:8]
miss=[r['case'] for r in checks if not r['r44_hit'] and r['case']>=232][:8]
ids=set(hit+miss+[200,201,202,203,90,91,93,95,99,101])
rows=[s for name in ['manifest','r41_holdout'] for s in Path(f'cases/{name}.txt').read_text().splitlines() if int(s.split()[0]) in ids]
assert len(rows)==len(ids)
Path('cases/r44_calibration.txt').write_text('\n'.join(rows)+'\n')
PY
python3 run_screen.py --baseline r41 --candidate r44 --manifest cases/r44_calibration.txt --tag r44_calibration --repeats 30 --discard 5 --windows 2 >logs/r44_calibration.log 2>&1
python3 archive_r42_r43.py >logs/r42_r43_archive.log
echo R44_DONE

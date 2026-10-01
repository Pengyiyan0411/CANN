#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_case12_k1_20261001
trap 'echo R60_FAILED > results/r60.status' ERR
echo R60_BUILD > results/r60.status
cmake -S . -B build >logs/r60_configure.log 2>&1
cmake --build build --target bench_r60 -j2 >logs/r60_build.log 2>&1
echo R60_PRECISION > results/r60.status
timeout 180 ./build/bench_r60 cases/all.txt 3 results/r60_correctness.jsonl >logs/r60_correctness.log 2>&1
python3 - <<'PY'
import json
from pathlib import Path
specs=json.loads(Path('cases/specs.json').read_text())
rows=[' '.join(str(s[k]) for k in ['id','B','M','N','K','dtype','ta','tb']) for s in specs if s['split']=='screen' and s['dtype']==1 and s['N'] in (4096,4160,5120,6080)]
assert len(rows)==8
Path('cases/r60_first8.txt').write_text('\n'.join(rows)+'\n')
PY
echo R60_SCREEN > results/r60.status
python3 run_screen.py --baseline r41 --candidate r60 --manifest cases/r60_first8.txt --tag r60_first8 --repeats 30 --discard 5 --windows 2 >logs/r60_first8.log 2>&1
echo R60_DONE > results/r60.status

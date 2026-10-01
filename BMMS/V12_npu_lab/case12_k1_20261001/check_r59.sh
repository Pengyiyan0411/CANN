#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_case12_k1_20261001
trap 'echo R59_FAILED > results/r59.status' ERR
echo R59_BUILD > results/r59.status
cmake -S . -B build >logs/r59_configure.log 2>&1
cmake --build build --target bench_r59 -j2 >logs/r59_build.log 2>&1
echo R59_PRECISION > results/r59.status
timeout 180 ./build/bench_r59 cases/all.txt 3 results/r59_correctness.jsonl >logs/r59_correctness.log 2>&1
python3 - <<'PY'
import json
from pathlib import Path
specs=json.loads(Path('cases/specs.json').read_text())
rows=[' '.join(str(s[k]) for k in ['id','B','M','N','K','dtype','ta','tb']) for s in specs if s['split']=='screen' and s['dtype']==1 and s['N'] in (4096,4160,5120,6080)]
assert len(rows)==8
Path('cases/r59_first8.txt').write_text('\n'.join(rows)+'\n')
PY
echo R59_SCREEN > results/r59.status
python3 run_screen.py --baseline r41 --candidate r59 --manifest cases/r59_first8.txt --tag r59_first8 --repeats 30 --discard 5 --windows 2 >logs/r59_first8.log 2>&1
echo R59_DONE > results/r59.status

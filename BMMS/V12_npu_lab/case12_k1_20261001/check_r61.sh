#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_case12_k1_20261001
trap 'echo R61_FAILED > results/r61.status' ERR
echo R61_BUILD > results/r61.status
cmake -S . -B build >logs/r61_configure.log 2>&1
cmake --build build --target bench_r61 -j2 >logs/r61_build.log 2>&1
echo R61_PRECISION > results/r61.status
timeout 180 ./build/bench_r61 cases/all.txt 3 results/r61_correctness.jsonl >logs/r61_correctness.log 2>&1
python3 - <<'PY'
import json
from pathlib import Path
specs=json.loads(Path('cases/specs.json').read_text())
rows=[' '.join(str(s[k]) for k in ['id','B','M','N','K','dtype','ta','tb']) for s in specs if s['split']=='screen' and s['dtype']==1 and s['N'] in (4096,4160,5120,6080)]
assert len(rows)==8
Path('cases/r61_first8.txt').write_text('\n'.join(rows)+'\n')
PY
timeout 180 ./build/bench_r61 cases_r59_extra/all.txt 5 results/r61_extra_precision.jsonl >logs/r61_extra_precision.log 2>&1
echo R61_SCREEN > results/r61.status
python3 run_screen.py --baseline r41 --candidate r61 --manifest cases/r61_first8.txt --tag r61_first8 --repeats 30 --discard 5 --windows 2 >logs/r61_first8.log 2>&1
echo R61_DONE > results/r61.status

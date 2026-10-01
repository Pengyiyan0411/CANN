#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_narrow_20260929
python3 run_screen.py --baseline r33 --candidate r41 --manifest cases/controls.txt --tag r41_controls --repeats 30 --discard 5 --windows 2 >logs/r41_controls.log 2>&1
python3 - <<'PY'
from pathlib import Path
import json
d=json.loads(Path('results/r41_holdout_summary.json').read_text())
ids={236,237,254,255}
for i in ids:
 assert any(r['case'][0]==i and r['version']=='r41' and any('bmms1241_' in k for k in r['kernels']) for r in d['runs'])
rows=[s for s in Path('cases/r41_holdout.txt').read_text().splitlines() if int(s.split()[0]) in ids]
assert len(rows)==4
Path('cases/r41_memory.txt').write_text('\n'.join(rows)+'\n')
PY
set +e
timeout -k 15 240 mssanitizer -t memcheck --log-file=results/r41_memcheck.log -- ./build/bench_r41 cases/r41_memory.txt 1 results/r41_memcheck.jsonl >logs/r41_memcheck_launcher.log 2>&1
status=$?
set -e
echo "$status" >results/r41_memcheck_status.txt
echo R41_FINAL_DONE

#!/usr/bin/env bash
set -eo pipefail
cd /home/developer/bmms_v12_lab_20260928
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
python3 - <<'PY'
from pathlib import Path
rows=[]
for line in Path('cases_shortk/manifest.txt').read_text().splitlines():
 i,B,M,N,K,dt,ta,tb=map(int,line.split())
 if (ta and M%64) or ((K if tb else N)%64):rows.append(line)
Path('cases_shortk/unaligned.txt').write_text('\n'.join(rows)+'\n')
PY
# Direct launch deliberately bypasses the current r32 AlignedPitch performance guard.
# This is synthetic coverage testing, with independent numeric gate before timing.
./build/event_bench_r32 cases_shortk/unaligned.txt 6 results/r32_unaligned_direct_event.jsonl >results/r32_unaligned_direct_event.log 2>&1
./build/event_bench_r32 cases_shortk/holdout.txt 8 results/r32_holdout_event.jsonl >results/r32_holdout_event.log 2>&1
python3 - <<'PY'
from pathlib import Path
from summarize_dense_next import events
import json
for tag,manifest in [('unaligned_direct','unaligned'),('holdout','holdout')]:
 s=events(Path(f'results/r32_{tag}_event.jsonl'),Path(f'cases_shortk/{manifest}.txt'))
 Path(f'results/r32_{tag}_summary.json').write_text(json.dumps(s,indent=2)+'\n')
 print(tag,{k:v for k,v in s.items() if k!='cases'})
 for x in s['cases']:print(x['case'],x['dims'],round(x['reduction_pct'],3))
PY

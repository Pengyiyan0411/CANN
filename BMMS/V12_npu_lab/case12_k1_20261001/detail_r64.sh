#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_case12_k1_20261001
test "$(cat results/r64.status)" = R64_DONE
echo R64_DETAIL_RUNNING > results/r64_detail.status
python3 - <<'PY'
from pathlib import Path
rows=[s for s in Path('cases/all.txt').read_text().splitlines() if int(s.split()[0]) in (1064,1125)]
assert len(rows)==2
Path('cases/r64_detail.txt').write_text('\n'.join(rows)+'\n')
PY
for version in r41 r63 r64; do
 tag=r64_detail_${version}
 msprof --output=profiles/$tag --task-time=on --ai-core=on --aic-metrics=PipeUtilization ./build/bench_$version cases/r64_detail.txt 5 results/$tag.jsonl >logs/$tag.log 2>&1
done
python3 summarize_r64_detail.py
echo R64_DETAIL_DONE > results/r64_detail.status

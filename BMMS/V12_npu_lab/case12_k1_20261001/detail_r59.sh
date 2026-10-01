#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_case12_k1_20261001
test "$(cat results/r59.status)" = R59_DONE
python3 - <<'PY'
from pathlib import Path
rows=[s for s in Path('cases/all.txt').read_text().splitlines() if int(s.split()[0]) in (1000,1005)]
assert len(rows)==2
Path('cases/r59_detail.txt').write_text('\n'.join(rows)+'\n')
PY
for metric in PipeUtilization Memory; do
  for version in r41 r59; do
    tag=r59_detail_${version}_${metric}
    msprof --output=profiles/$tag --task-time=on --ai-core=on --aic-metrics=$metric ./build/bench_$version cases/r59_detail.txt 5 results/$tag.jsonl >logs/$tag.log 2>&1
  done
done
echo R59_DETAIL_DONE > results/r59_detail.status

#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_case12_k1_20261001
python3 - <<'PY'
from pathlib import Path
rows=[s for s in Path('cases/r54_memory.txt').read_text().splitlines() if s.startswith('1007 ')]
assert len(rows)==1
Path('cases/r54_memory_tail.txt').write_text(rows[0]+'\n')
PY
set +e
timeout -k 15 120 mssanitizer -t memcheck --log-file=san_r54/memcheck_full_tail.log -- ./build/sanitize_r54 cases/r54_memory_tail.txt 1 san_r54/tail_precision.jsonl > logs/r54_memcheck_full_tail_launcher.log 2>&1
status=$?
set -e
echo "$status" > results/r54_memcheck_full_tail_status.txt
echo MEMCHECK_TAIL_FINISHED

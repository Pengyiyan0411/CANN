#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_case12_k1_20261001
mkdir -p san_r54
chmod 750 san_r54
cmake --build build --target sanitize_r54 -j2 >logs/r54_sanitize_build.log 2>&1
python3 - <<'PY'
from pathlib import Path
rows=[s for s in Path('cases/all.txt').read_text().splitlines() if int(s.split()[0]) in [1004,1005,1006,1007]]
assert len(rows)==4
Path('cases/r54_memory.txt').write_text('\n'.join(rows)+'\n')
PY
set +e
timeout -k 15 180 mssanitizer -t memcheck --block-id=0 --log-file=san_r54/memcheck.log -- ./build/sanitize_r54 cases/r54_memory.txt 1 san_r54/precision.jsonl >logs/r54_memcheck_launcher.log 2>&1
status=$?
set -e
echo "$status" >results/r54_memcheck_status.txt
echo SANITIZER_FINISHED

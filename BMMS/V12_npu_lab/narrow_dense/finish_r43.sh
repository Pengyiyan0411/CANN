#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_narrow_20260929
python3 run_screen.py --baseline r41 --candidate r43 --manifest cases/r43_holdout.txt --tag r43_holdout --repeats 30 --discard 5 --windows 2 >logs/r43_holdout.log 2>&1
python3 - <<'PY'
from pathlib import Path
p=Path('cases')
lines=[r for r in (p/'controls.txt').read_text().splitlines() if int(r.split()[0]) not in [93,94]]
lines += [r for r in (p/'r41_holdout.txt').read_text().splitlines() if int(r.split()[0]) in [200,201,202,203,232,233]]
(p/'r43_controls.txt').write_text('\n'.join(lines)+'\n')
lines=[r for r in (p/'r43_values.txt').read_text().splitlines() if int(r.split()[0]) in [366,367]]
(p/'r43_memory.txt').write_text('\n'.join(lines)+'\n')
PY
python3 run_screen.py --baseline r41 --candidate r43 --manifest cases/r43_controls.txt --tag r43_controls --repeats 30 --discard 5 --windows 2 >logs/r43_controls.log 2>&1
mkdir -p -m 750 san_r43
chmod 750 san_r43
set +e
timeout -k 15 180 mssanitizer -t memcheck --log-file=san_r43/memcheck.log -- ./build/bench_r43 cases/r43_memory.txt 1 san_r43/precision.jsonl >logs/r43_memcheck.log 2>&1
status=$?
set -e
echo "$status" >san_r43/status.txt
python3 archive_r42_r43.py >logs/r42_r43_archive.log
echo R43_FINAL_DONE

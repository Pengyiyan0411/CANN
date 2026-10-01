#!/usr/bin/env bash
set -eo pipefail
cd /home/developer/bmms_v12_lab_20260928
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
python3 generate_native_final.py >results/native_final_generation_with_env.log 2>&1
python3 - <<'PY'
from pathlib import Path
p=Path('cases_native_final')
(p/'n64_medium.txt').write_text(''.join(x+'\n' for x in (p/'manifest.txt').read_text().splitlines() if 24<=int(x.split()[0])<32 or 40<=int(x.split()[0])<48))
PY
./build/bench_r36 cases_native_final/n64_medium.txt 3 results/r36_guard_correctness.jsonl >results/r36_guard_correctness.log 2>&1
./build/event_bench_r36 cases_native_final/n64_medium.txt 10 results/r36_guard_event.jsonl >results/r36_guard_event.log 2>&1
echo GUARD_DONE

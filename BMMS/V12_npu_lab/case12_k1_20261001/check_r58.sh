#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_case12_k1_20261001
test "$(cat results/r57.status)" = R57_DONE
trap 'echo R58_FAILED > results/r58.status' ERR
python3 - <<'PY'
from pathlib import Path
p=Path('CMakeLists.txt');s=p.read_text();s=s.replace('foreach(v r41 r51 r52 r53 r54 r55 r56 r57)','foreach(v r41 r51 r52 r53 r54 r55 r56 r57 r58)');p.write_text(s)
PY
echo R58_BUILD > results/r58.status
cmake -S . -B build >logs/r58_configure.log 2>&1
cmake --build build --target bench_r58 -j2 >logs/r58_build.log 2>&1
echo R58_PRECISION > results/r58.status
timeout 180 ./build/bench_r58 cases/all.txt 3 results/r58_correctness.jsonl >logs/r58_correctness.log 2>&1
echo R58_CALIBRATION > results/r58.status
python3 run_screen.py --baseline r41 --candidate r58 --manifest cases/screen.txt --tag r58_calibration --repeats 12 --discard 3 --windows 2 >logs/r58_calibration.log 2>&1
python3 run_screen.py --baseline r41 --candidate r58 --manifest cases/guards.txt --tag r58_fallback --repeats 12 --discard 3 --windows 2 >logs/r58_fallback.log 2>&1
echo R58_DONE > results/r58.status

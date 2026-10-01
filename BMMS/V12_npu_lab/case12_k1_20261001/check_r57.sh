#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_case12_k1_20261001
test "$(cat results/r56.status)" = R56_DONE
trap 'echo R57_FAILED > results/r57.status' ERR
python3 - <<'PY'
from pathlib import Path
p=Path('CMakeLists.txt');s=p.read_text();s=s.replace('foreach(v r41 r51 r52 r53 r54 r55 r56)','foreach(v r41 r51 r52 r53 r54 r55 r56 r57)');p.write_text(s)
PY
echo R57_BUILD > results/r57.status
cmake -S . -B build >logs/r57_configure.log 2>&1
cmake --build build --target bench_r57 -j2 >logs/r57_build.log 2>&1
echo R57_PRECISION > results/r57.status
timeout 180 ./build/bench_r57 cases/all.txt 3 results/r57_correctness.jsonl >logs/r57_correctness.log 2>&1
echo R57_SCREEN > results/r57.status
python3 run_screen.py --baseline r41 --candidate r57 --manifest cases/screen.txt --tag r57_screen --repeats 30 --discard 5 --windows 2 >logs/r57_screen.log 2>&1
echo R57_DONE > results/r57.status

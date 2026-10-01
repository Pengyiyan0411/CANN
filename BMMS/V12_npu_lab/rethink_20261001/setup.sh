#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_rethink_20261001
mkdir -p logs results profiles cases
trap 'echo SETUP_FAILED > results/setup.status' ERR
echo BUILD > results/setup.status
tar -xzf catlass_headers.tar.gz
python3 - <<'PY'
from pathlib import Path
old=Path('/home/developer/bmms_case12_k1_20261001/cases')
for p in old.glob('*'):
 if p.is_file() and not (Path('cases')/p.name).exists():(Path('cases')/p.name).symlink_to(p)
rows=old.joinpath('all.txt').read_text().splitlines()
Path('cases/gemm_smoke.txt').write_text('\n'.join(s for s in rows if int(s.split()[0]) in [1000,1001,1002,1003])+'\n')
Path('cases/gemm_scope.txt').write_text('\n'.join(s for s in rows if 1000<=int(s.split()[0])<1148)+'\n')
PY
cmake -S . -B build >logs/configure.log 2>&1
for v in cat0 cat1 native; do
 echo "BUILD_${v}" > results/setup.status
 cmake --build build --target "gemm_${v}" -j2 >"logs/build_${v}.log" 2>&1
 echo "SMOKE_${v}" > results/setup.status
 timeout -k 15 90 "./build/gemm_${v}" cases/gemm_smoke.txt 2 "results/${v}_smoke.jsonl" >"logs/smoke_${v}.log" 2>&1
done
echo SETUP_DONE > results/setup.status

#!/usr/bin/env bash
set -eo pipefail
cd /home/developer/bmms_v12_lab_20260928
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cmake -S . -B build >logs/r25_configure.log 2>&1
cmake --build build --target r25_build -j2 >logs/r25_build.log 2>&1
echo R25_BUILD_DONE
python3 generate_r25_values.py >results/r25_values_generate.log 2>&1
for pair in 'screen cases_c1112_screen' 'values cases_r25_values'; do
 read -r label dir <<< "$pair"
 ./build/bench_r25 "$dir/manifest.txt" 3 "results/r25_${label}_correctness.jsonl" >"results/r25_${label}_correctness.log" 2>&1
done
python3 - <<'PY'
from pathlib import Path
for name in ['cases_c1112_screen','cases_c1112_holdout']:
 p=Path(name);lines=[]
 for line in (p/'manifest.txt').read_text().splitlines():
  i,B,M,N,K,dt,ta,tb=map(int,line.split())
  if (not ta or M%64==0) and (K if tb else N)%64==0:lines.append(line)
 (p/'aligned.txt').write_text('\n'.join(lines)+'\n')
 print(name,'aligned configs',len(lines))
PY
./build/event_bench_r25 cases_c1112_screen/aligned.txt 6 results/r25_screen_event.jsonl >results/r25_screen_event.log 2>&1
echo R25_SCREEN_DONE

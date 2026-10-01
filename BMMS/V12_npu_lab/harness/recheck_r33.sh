#!/usr/bin/env bash
set -eo pipefail
cd /home/developer/bmms_v12_lab_20260928
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
python3 - <<'PY'
from pathlib import Path
p=Path('cases_c1112_holdout')
lines={int(s.split()[0]):s for s in (p/'manifest.txt').read_text().splitlines()}
(p/'unchanged_recheck.txt').write_text('\n'.join(lines[i] for i in [63,61,62,60,0,1])+'\n')
s=Path('run_screen.py').read_text()
s=s.replace('pair=[args.baseline,args.candidate] if w%2==0 else [args.candidate,args.baseline]',
            'pair=[args.candidate,args.baseline] if w%2==0 else [args.baseline,args.candidate]')
Path('run_screen_reverse.py').write_text(s)
PY
python3 run_screen_reverse.py --baseline r30 --candidate r33 --manifest cases_c1112_holdout/unchanged_recheck.txt --tag r33_unchanged_reverse --repeats 80 --discard 20 --windows 4 >results/r33_unchanged_reverse.log 2>&1
python3 run_screen_reverse.py --baseline r30 --candidate r33 --manifest cases_split_controls/c8_unaffected.txt --tag r33_small_reverse --repeats 100 --discard 25 --windows 4 >results/r33_small_reverse.log 2>&1
echo RECHECK_DONE

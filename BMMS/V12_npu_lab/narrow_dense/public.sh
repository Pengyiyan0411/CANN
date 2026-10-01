#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_narrow_20260929
python3 run_screen.py --baseline r33 --candidate r37 --manifest cases/public.txt --tag r37_public --repeats 60 --discard 15 --windows 2 >logs/r37_public.log 2>&1
python3 run_screen.py --baseline r33 --candidate r37 --manifest cases/controls.txt --tag r37_controls --repeats 60 --discard 15 --windows 2 >logs/r37_controls.log 2>&1
echo PROFILING_DONE

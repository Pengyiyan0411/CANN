#!/usr/bin/env bash
set -eo pipefail
cd /home/developer/bmms_v12_lab_20260928
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
# r22 first, opposite starting order; 4 windows per executable.
python3 run_screen.py --baseline r22 --candidate r19 --manifest cases_split_controls/c8_unaffected.txt --tag c1112_r22_other_reverse --repeats 100 --discard 30 --windows 4 >results/c1112_r22_other_reverse.log 2>&1
echo C1112_CONTROL_RECHECK_DONE

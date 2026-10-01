#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_case12_k1_20261001
trap 'echo HOLDOUT_FAILED > results/r53_holdout.status' ERR
python3 run_screen.py --baseline r41 --candidate r53 --manifest cases/holdout.txt --tag r53_holdout --repeats 30 --discard 5 --windows 2 > logs/r53_holdout.log 2>&1
echo HOLDOUT_DONE > results/r53_holdout.status

from pathlib import Path
r=Path(__file__).resolve().parent;h=r/'harness'
g=(h/'generate_c12_holdout.py').read_text(encoding='utf-8');a=g.index('specs=[]');b=g.index('manifest=[];records=[]')
s='''specs=[]
import random
rng=random.Random(202092803)
for i in range(32):
 M=16*rng.randrange(64,257);N=16*rng.randrange(64,257);K=32*rng.randrange(48,64)
 if i>=24:
  if i%2:M=16*rng.randrange(257,513)
  else:N=16*rng.randrange(257,513)
 specs.append(dict(id=i,label='c12_frozen_policy_random',B=1,M=M,N=N,K=K,dtype=1+(i//4)%2,ta=(i//2)%2,tb=i%2,pattern='random'))
'''
g=g[:a]+s+g[b:];g=g.replace('cases_c12_holdout','cases_c12_random').replace('2092802','202092804')
g=g.replace("sets={'manifest':range(len(manifest)),'profile':[4], 'sanitize':[6,7], 'screen':range(24)}","sets={'manifest':range(len(manifest)),'screen':range(len(manifest))}")
(h/'generate_c12_random.py').write_text(g,encoding='utf-8',newline='\n')
script='''#!/usr/bin/env bash
set -eo pipefail
cd /home/developer/bmms_v12_lab_20260928
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
python3 generate_c12_random.py >results/c12_random_generate.log 2>&1
./build/bench_r19 cases_c12_random/manifest.txt 3 results/c12_r19_random_correctness.jsonl >results/c12_r19_random_correctness.log 2>&1
./build/bench_r20 cases_c12_random/manifest.txt 3 results/c12_r20_random_correctness.jsonl >results/c12_r20_random_correctness.log 2>&1
./build/event_bench_r20 cases_c12_random/manifest.txt 10 results/c12_r20_random_event.jsonl >results/c12_r20_random_event.log 2>&1
./build/event_bench_r20 cases_c12_random/manifest.txt 10 results/c12_r20_random_event_repeat.jsonl >results/c12_r20_random_event_repeat.log 2>&1
bash regress_c12_r20.sh
echo C12_R20_RANDOM_DONE
'''
(h/'check_c12_random.sh').write_text(script,encoding='utf-8',newline='\n')
p=h/'regress_c12_r20.sh';p.write_text(p.read_text(encoding='utf-8'),encoding='utf-8',newline='\n')
p=h/'analyze_c12_r20.py';t=p.read_text(encoding='utf-8');t=t.replace("['holdout_event','holdout_event_repeat','aa']","['holdout_event','holdout_event_repeat','random_event','random_event_repeat','aa']");p.write_text(t,encoding='utf-8',newline='\n')

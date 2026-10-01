"""Serial diagnostics after r67, using fixed two-shape counter sample."""
import csv,json,statistics,subprocess
from pathlib import Path
root=Path(__file__).resolve().parent
assert root.joinpath('results/r67.status').read_text().strip()=='R67_DONE'
# Only the no-shuffle pretrained template passed precision; never profile the failed candidate as viable.
sc=root.joinpath('run_preload_audit.py').read_text()
sc=sc.replace("['native','pre0','pre1']","['native','pre0']").replace("['pre1','pre0','native']","['pre0','native']")
root.joinpath('run_preload_valid.py').write_text(sc)
with root.joinpath('logs/preload_valid.log').open('w') as f:
 subprocess.run(['python3','run_preload_valid.py'],cwd=root,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=300)
rows=[s for s in root.joinpath('cases/all.txt').read_text().splitlines() if int(s.split()[0]) in (1064,1125)]
root.joinpath('cases/rethink_detail.txt').write_text('\n'.join(rows)+'\n')
cases=[list(map(int,s.split())) for s in rows];items=[]
for v in ['r41','r65','r66','r67']:
 dest=root/'profiles'/f'detail_{v}'
 assert not dest.exists()
 cmd=['msprof',f'--output={dest}','--task-time=on','--ai-core=on','--aic-metrics=PipeUtilization',f'./build/bench_{v}',
      'cases/rethink_detail.txt','5',f'results/detail_{v}.jsonl']
 with root.joinpath(f'logs/detail_{v}.log').open('w') as f:
  subprocess.run(cmd,cwd=root,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
 val=[json.loads(s) for s in root.joinpath(f'results/detail_{v}.jsonl').read_text().splitlines()]
 assert all(x['pass'] for x in val) and len(val)==len(cases)
 paths=list(dest.glob('PROF_*/mindstudio_profiler_output/op_summary*.csv'));assert len(paths)==1
 raw=[x for x in csv.DictReader(paths[0].open()) if 'bmms' in x.get('Op Name','')]
 raw.sort(key=lambda x:float(x['Task Start Time(us)']));assert len(raw)==10
 for i,c in enumerate(cases):
  group=raw[i*5+1:(i+1)*5];means={}
  for key in group[0]:
   try:means[key]=statistics.median(float(x[key]) for x in group)
   except ValueError:pass
  items.append(dict(version=v,case=c,medians=means,raw=group))
root.joinpath('results/detail_counters.json').write_text(json.dumps(items,indent=2)+'\n')
root.joinpath('results/followup.status').write_text('FOLLOWUP_DONE\n')

from pathlib import Path
import csv,json,statistics,subprocess
root=Path(__file__).resolve().parent
manifest='cases/r59_first8.txt'
cases=[list(map(int,s.split())) for s in (root/manifest).read_text().splitlines() if s.strip()]
repeats=25;discard=5;runs=[]
for window,versions in enumerate([['native','pre0','pre1'],['pre1','pre0','native']]):
 for version in versions:
  tag=f'preload_{version}_w{window}'
  exe='/home/developer/bmms_case12_k1_20261001/build/bench_r41' if version=='r41' else f'./build/gemm_{version}'
  dest=root/'profiles'/tag;assert not dest.exists()
  command=['msprof',f'--output={dest}','--task-time=on','--ai-core=off',exe,manifest,str(repeats),f'results/{tag}.jsonl']
  with (root/f'logs/{tag}.log').open('w') as log:subprocess.run(command,cwd=root,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
  validity=[json.loads(s) for s in (root/f'results/{tag}.jsonl').read_text().splitlines()]
  assert len(validity)==len(cases) and all(s['pass'] for s in validity)
  paths=list(dest.glob('PROF_*/mindstudio_profiler_output/op_summary*.csv'));assert len(paths)==1,paths
  rows=list(csv.DictReader(paths[0].open()))
  rows=[r for r in rows if 'bmms' in r.get('Op Name','') or 'KernelAdapter' in r.get('Op Name','')]
  rows.sort(key=lambda x:float(x['Task Start Time(us)']))
  assert len(rows)==len(cases)*repeats,(version,len(rows),[(r.get('Op Name'),r.get('Task Type')) for r in rows[:3]])
  for i,case in enumerate(cases):
   group=rows[i*repeats:(i+1)*repeats];times=[float(r['Task Duration(us)']) for r in group[discard:]]
   item=dict(version=version,window=window,case=case,median_us=statistics.median(times),raw_us=times,kernels=sorted({r['Op Name'] for r in group}))
   runs.append(item);print({k:item[k] for k in ['version','window','case','median_us']},flush=True)
  (root/'results/preload_audit_partial.json').write_text(json.dumps(runs,indent=2)+'\n')
summary=[]
for case in cases:
 row={'case':case}
 for version in ['native','pre0','pre1']:
  times=[r['median_us'] for r in runs if r['version']==version and r['case']==case]
  row[version]={'window_medians_us':times,'median_us':statistics.median(times)}
 summary.append(row)
(root/'results/preload_audit.json').write_text(json.dumps(dict(note='r41 is full fused BMMS; other three are GEMM-only full FP32 C, not equivalent complete operator timings; memory/output protocol and scheduler differ',repeats=repeats,discard=discard,summary=summary,runs=runs),indent=2)+'\n')
print(json.dumps(summary,indent=2))

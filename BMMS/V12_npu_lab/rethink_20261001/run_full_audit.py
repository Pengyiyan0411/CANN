from pathlib import Path
import csv,json,statistics,subprocess
root=Path(__file__).resolve().parent;manifest='cases/r59_first8.txt'
cases=[list(map(int,s.split())) for s in (root/manifest).read_text().splitlines() if s.strip()]
runs=[];repeats=25;discard=5
for window,versions in enumerate([['r41','fullcat1'],['fullcat1','r41']]):
 for v in versions:
  tag=f'full_{v}_w{window}';dest=root/'profiles'/tag;assert not dest.exists()
  exe='/home/developer/bmms_case12_k1_20261001/build/bench_r41' if v=='r41' else './build/gemm_fullcat1'
  with (root/f'logs/{tag}.log').open('w') as log:subprocess.run(['msprof',f'--output={dest}','--task-time=on','--ai-core=off',exe,manifest,str(repeats),f'results/{tag}.jsonl'],cwd=root,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
  vals=[json.loads(s) for s in (root/f'results/{tag}.jsonl').read_text().splitlines()];assert len(vals)==len(cases) and all(x['pass'] for x in vals)
  paths=list(dest.glob('PROF_*/mindstudio_profiler_output/op_summary*.csv'));assert len(paths)==1
  rows=[r for r in csv.DictReader(paths[0].open()) if 'bmms' in r.get('Op Name','') or 'KernelAdapter' in r.get('Op Name','')]
  rows.sort(key=lambda r:float(r['Task Start Time(us)']));n=1 if v=='r41' else 3
  assert len(rows)==len(cases)*repeats*n,(v,len(rows))
  for i,case in enumerate(cases):
   group=rows[i*repeats*n:(i+1)*repeats*n];spans=[];sums=[];stages=[[] for _ in range(n)]
   for rep in range(discard,repeats):
    chunk=group[rep*n:(rep+1)*n];ts=[float(r['Task Duration(us)']) for r in chunk]
    spans.append(float(chunk[-1]['Task Start Time(us)'])+ts[-1]-float(chunk[0]['Task Start Time(us)']));sums.append(sum(ts))
    for k,t in enumerate(ts):stages[k].append(t)
   item=dict(version=v,window=window,case=case,median_span_us=statistics.median(spans),median_task_sum_us=statistics.median(sums),stage_medians_us=[statistics.median(t) for t in stages],kernels=sorted({r['Op Name'] for r in group}),raw_span_us=spans)
   runs.append(item);print(item['version'],case,item['median_span_us'],item['stage_medians_us'],flush=True)
  (root/'results/full_audit_partial.json').write_text(json.dumps(runs,indent=2)+'\n')
(root/'results/full_audit.json').write_text(json.dumps(dict(note='fullcat1 is three device kernels, includes device scheduling gaps in span; task sum separately shown. r41 fused one kernel. No claim of optimized reduction.',runs=runs),indent=2)+'\n')

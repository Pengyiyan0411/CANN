"""Serial correctness-gated A/B/B/A task-time screening, never two NPU jobs."""
import argparse
import csv
import hashlib
import json
import statistics
import subprocess
import time
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('--candidate',default='r07')
p.add_argument('--baseline',default='r03')
p.add_argument('--manifest',default='cases_followup/screen_r06.txt')
p.add_argument('--tag',default='r07_screen')
p.add_argument('--repeats',type=int,default=40)
p.add_argument('--discard',type=int,default=10)
p.add_argument('--windows',type=int,default=2)
args=p.parse_args()
root=Path(__file__).resolve().parent
cases=[list(map(int,line.split())) for line in (root/args.manifest).read_text().splitlines() if line.strip()]
runs=[]
order=[]
for w in range(args.windows):
    pair=[args.baseline,args.candidate] if w%2==0 else [args.candidate,args.baseline]
    order.extend((v,w) for v in pair)
for version,w in order:
    tag=f'{args.tag}_{version}_w{w}'
    output=root/'profiles'/tag
    assert not output.exists(),f'Run id already exists: {output}'
    cmd=['msprof',f'--output={output}','--task-time=on','--ai-core=off',f'./build/bench_{version}',
         args.manifest,str(args.repeats),f'results/{tag}.jsonl']
    with (root/f'results/{tag}.log').open('w') as log:
        subprocess.run(cmd,cwd=root,stdout=log,stderr=subprocess.STDOUT,timeout=150,check=True)
    validation=[json.loads(s) for s in (root/f'results/{tag}.jsonl').read_text().splitlines()]
    assert len(validation)==len(cases) and all(r['pass'] for r in validation),tag
    files=list(output.glob('PROF_*/mindstudio_profiler_output/op_summary*.csv'))
    assert len(files)==1,files
    rows=[r for r in csv.DictReader(files[0].open()) if 'bmms' in r.get('Op Name','')]
    rows.sort(key=lambda r:float(r['Task Start Time(us)']))
    assert len(rows)==len(cases)*args.repeats,(tag,len(rows))
    for i,case in enumerate(cases):
        group=rows[i*args.repeats:(i+1)*args.repeats]
        values=[float(r['Task Duration(us)']) for r in group[args.discard:]]
        run=dict(run=tag,version=version,window=w,case=case,
                 kernels=sorted({r['Op Name'] for r in group}),median_us=statistics.median(values),
                 mean_us=statistics.mean(values),min_us=min(values),max_us=max(values),raw_us=values)
        runs.append(run)
        print({k:run[k] for k in ['run','case','median_us']},flush=True)
summary=[]
for case in cases:
    rs=[r for r in runs if r['case']==case]
    aa=[r['median_us'] for r in rs if r['version']==args.baseline]
    bb=[r['median_us'] for r in rs if r['version']==args.candidate]
    ratio=[aa[i]/bb[i] for i in range(len(aa))]
    summary.append(dict(case=case,baseline_medians_us=aa,candidate_medians_us=bb,speedups=ratio,
                        baseline_median_us=statistics.median(aa),candidate_median_us=statistics.median(bb)))
report=dict(kind='lightweight_profiler_task_time_not_unprofiled_benchmark',
            synthetic_not_hidden=True,manifest=args.manifest,repeats=args.repeats,discard=args.discard,
            source_sha256={v:hashlib.sha256((root/f'{v}.asc').read_bytes()).hexdigest() for v in [args.baseline,args.candidate]},
            independent_windows_per_version=args.windows,summary=summary,runs=runs)
(root/f'results/{args.tag}_summary.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(summary,indent=2))

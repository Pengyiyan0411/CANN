import csv
import json
import statistics
from pathlib import Path

root=Path(__file__).resolve().parent
summary=[]
for p in sorted((root/'profiles').glob('*/PROF_*/mindstudio_profiler_output/op_summary*.csv')):
    rows=list(csv.DictReader(p.open()))
    rows=[r for r in rows if 'bmms' in r.get('Op Name','')]
    rows.sort(key=lambda r:float(r['Task Start Time(us)']))
    if len(rows)!=40:raise RuntimeError(f'{p}: expected 40 kernel tasks, got {len(rows)}')
    values=[float(r['Task Duration(us)']) for r in rows][10:]
    name=p.parents[2].name
    metrics={}
    for k in ['aicore_time(us)','aic_mac_time(us)','aic_scalar_time(us)','aic_mte1_time(us)','aic_mte2_time(us)','aic_fixpipe_time(us)','aiv_time(us)','aiv_vec_time(us)','aiv_scalar_time(us)']:
        if k in rows[0]:metrics[k]=statistics.median(float(r[k]) for r in rows[10:])
    summary.append(dict(run=name,mode='pipe_metrics' if metrics else 'task_time_only',metrics_median=metrics,kernel_names=sorted({r['Op Name'] for r in rows}),
        tasks=len(rows),discarded=10,samples=len(values),median_us=statistics.median(values),
        mean_us=statistics.mean(values),min_us=min(values),max_us=max(values),raw_us=values))
report={'kind':'lightweight_profiler_task_time_not_unprofiled_benchmark',
        'shape':[1,1024,2048,1024],'dtype':'float16','ta':False,'tb':False,
        'synthetic_not_hidden_case9':True,'runs':summary}
for r in summary:print({k:v for k,v in r.items() if k not in ('raw_us','kernel_names')})
(root/'results/profile_summary.json').write_text(json.dumps(report,indent=2)+'\n')

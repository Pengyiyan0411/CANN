import csv
import json
import statistics as st
from pathlib import Path

root=Path(__file__).resolve().parent
output={}
for path in sorted((root/'results').glob('r*_event_*.jsonl')):
    rows=[json.loads(s) for s in path.read_text().splitlines()]
    report=[]
    for cid in sorted({r['case'] for r in rows}):
        subset=[r for r in rows if r['case']==cid]
        a={r['window']:r['device_stream_us_per_call'] for r in subset if r['label']=='A'}
        b={r['window']:r['device_stream_us_per_call'] for r in subset if r['label']=='B'}
        assert a.keys()==b.keys()
        reductions=[100*(1-b[w]/a[w]) for w in a]
        report.append(dict(case=cid,windows=len(a),baseline_us=st.median(a.values()),
                           candidate_us=st.median(b.values()),median_paired_reduction_pct=st.median(reductions),
                           min_paired_reduction_pct=min(reductions),max_paired_reduction_pct=max(reductions)))
    output[path.stem]=report
    print(path.stem,report)

files=list((root/'profiles/native_metrics').glob('PROF_*/mindstudio_profiler_output/op_summary*.csv'))
if len(files)==1:
    rows=[r for r in csv.DictReader(files[0].open()) if 'bmms' in r.get('Op Name','')]
    rows.sort(key=lambda r:float(r['Task Start Time(us)']))
    cases=[list(map(int,s.split())) for s in (root/'cases_followup/screen_native.txt').read_text().splitlines()]
    assert len(rows)==20*len(cases)
    report=[]
    for i,case in enumerate(cases):
        group=rows[i*20+5:(i+1)*20]
        fields=['Task Duration(us)','aicore_time(us)','aic_mac_time(us)','aic_scalar_time(us)',
                'aic_mte1_time(us)','aic_mte2_time(us)','aic_fixpipe_time(us)','aiv_time(us)',
                'aiv_vec_time(us)','aiv_scalar_time(us)']
        report.append(dict(case=case,kernels=sorted({r['Op Name'] for r in group}),
                           metrics={k:st.median(float(r[k]) for r in group) for k in fields if k in group[0]}))
    output['native_metrics']=report
    print('native_metrics',report)
(root/'results/followup_analysis.json').write_text(json.dumps(output,indent=2)+'\n')

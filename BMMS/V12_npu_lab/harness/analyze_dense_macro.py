from pathlib import Path
import json,statistics
r=Path(__file__).resolve().parent
def analyze(p):
 rows=[json.loads(x) for x in p.read_text().splitlines()];report=[]
 for case in sorted({x['case'] for x in rows}):
  a=[x['device_stream_us_per_call'] for x in rows if x['case']==case and x['label']=='A']
  b=[x['device_stream_us_per_call'] for x in rows if x['case']==case and x['label']=='B']
  assert len(a)==len(b) and len(a)>=2
  aa,bb=statistics.median(a),statistics.median(b)
  report.append(dict(case=case,base_us=aa,candidate_us=bb,improvement_pct=(1-bb/aa)*100,
    paired_improvements_pct=[(1-y/x)*100 for x,y in zip(a,b)]))
 return dict(file=p.name,median_improvement_pct=statistics.median(x['improvement_pct'] for x in report),
  min_improvement_pct=min(x['improvement_pct'] for x in report),max_improvement_pct=max(x['improvement_pct'] for x in report),cases=report)
for v in [25,26,27]:
 for kind in ['screen','holdout','holdout_repeat']:
  p=r/f'results/r{v}_{kind}_event.jsonl'
  if p.exists():
   q=analyze(p);(r/f'results/r{v}_{kind}_analysis.json').write_text(json.dumps(q,indent=2)+'\n')
   print(json.dumps(q),flush=True)

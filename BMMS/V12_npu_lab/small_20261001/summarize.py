import json,statistics,sys
from pathlib import Path
root=Path(__file__).resolve().parent
for name in sys.argv[1:]:
 p=root/'results'/name;report=json.loads(p.read_text());s=report['summary']
 def agg(rows):
  gains=[100*(1-r['candidate_median_us']/r['baseline_median_us']) for r in rows]
  return dict(n=len(rows),median_reduction_pct=statistics.median(gains),min_reduction_pct=min(gains),max_reduction_pct=max(gains),
              median_delta_us=statistics.median(r['baseline_median_us']-r['candidate_median_us'] for r in rows),
              regress_over3pct=sum(g< -3 for g in gains),win_over5pct=sum(g>=5 for g in gains))
 out=dict(file=name,all=agg(s))
 for key,col in [('B',1),('dtype',5)]:
  out[key]={str(x):agg([r for r in s if r['case'][col]==x]) for x in sorted({r['case'][col] for r in s})}
 print(json.dumps(out,indent=2))
 (root/'results'/name.replace('_summary.json','_aggregate.json')).write_text(json.dumps(out,indent=2)+'\n')

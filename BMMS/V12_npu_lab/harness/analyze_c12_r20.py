from pathlib import Path
from collections import defaultdict
import json,statistics as st
r=Path(__file__).resolve().parent
for suffix in ['holdout_event','holdout_event_repeat','random_event','random_event_repeat','aa']:
 p=r/f'results/c12_r20_{suffix}.jsonl'
 if not p.exists():continue
 g=defaultdict(lambda:defaultdict(list));chosen=set()
 for l in p.read_text().splitlines():
  x=json.loads(l);g[x['case']][x['label']].append(x['device_stream_us_per_call'])
  if x['kernel']=='r20':chosen.add(x['case'])
 rows=[]
 for i,t in sorted(g.items()):
  if not t['A'] or not t['B']:continue
  a=st.median(t['A']);b=st.median(t['B']);rows.append(dict(case=i,baseline_us=a,candidate_us=b,selected=i in chosen,reduction_pct=100*(1-b/a),windows=min(len(t['A']),len(t['B']))))
 if not rows:continue
 stats={}
 for k,rs in [('all',rows),('selected',[x for x in rows if x['selected']]),('fallback',[x for x in rows if not x['selected']])]:
  if rs:stats[k]=dict(count=len(rs),median=st.median(x['reduction_pct'] for x in rs),min=min(x['reduction_pct'] for x in rs),max=max(x['reduction_pct'] for x in rs))
 (r/f'results/c12_r20_{suffix}_summary.json').write_text(json.dumps(dict(stats=stats,cases=rows),indent=2)+'\n')
 print(suffix,stats)
 for x in rows:print(x['case'],x['selected'],round(x['baseline_us'],2),round(x['candidate_us'],2),round(x['reduction_pct'],2),x['windows'])

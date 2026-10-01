import json,statistics as st
from pathlib import Path
from collections import defaultdict
root=Path(__file__).resolve().parent
meta={x['id']:x for x in (json.loads(l) for l in (root/'cases_c12_screen/manifest.jsonl').read_text().splitlines())}
for variant in ['packet2','packet1']:
 p=root/f'results/c12_{variant}_event.jsonl'
 if not p.exists():continue
 groups=defaultdict(lambda:defaultdict(list))
 for line in p.read_text().splitlines():
  try:x=json.loads(line)
  except ValueError:continue
  groups[x['case']][x['label']].append(x['device_stream_us_per_call'])
 result=[]
 for i,g in sorted(groups.items()):
  if min(len(g['A']),len(g['B']))<6:continue
  a=st.median(g['A']);b=st.median(g['B']);s=meta[i]
  result.append(dict(case=i,M=s['M'],N=s['N'],K=s['K'],dtype=s['dtype'],ta=s['ta'],tb=s['tb'],baseline_us=a,candidate_us=b,reduction_pct=100*(1-b/a)))
 if not result:continue
 report=dict(variant=variant,count=len(result),median=st.median(x['reduction_pct'] for x in result),min=min(x['reduction_pct'] for x in result),max=max(x['reduction_pct'] for x in result),cases=result)
 (root/f'results/c12_{variant}_summary.json').write_text(json.dumps(report,indent=2)+'\n')
 print(variant,report['count'],'median/min/max',*[round(report[k],2) for k in ['median','min','max']])
 for x in result:print(x['case'],x['M'],x['N'],str(x['ta'])+str(x['tb']),round(x['baseline_us'],2),round(x['candidate_us'],2),round(x['reduction_pct'],2))

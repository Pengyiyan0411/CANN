from pathlib import Path
import json,statistics,collections
out=Path(__file__).resolve().parent/'results/plan_equal_20260929'
for tag in ['r41_discovery','r41_holdout']:
 p=out/(tag+'_summary.json')
 if not p.exists():continue
 data=json.loads(p.read_text());rows=[]
 for r in data['summary']:
  runs=[x for x in data['runs'] if x['case']==r['case'] and x['version']=='r41']
  active=any('bmms1241_' in k for x in runs for k in x['kernels'])
  reduction=100*(1-r['candidate_median_us']/r['baseline_median_us'])
  rows.append(dict(case=r['case'],active=active,reduction_percent=reduction,baseline_us=r['baseline_median_us'],candidate_us=r['candidate_median_us'],windows=[100*(1-b/a) for a,b in zip(r['baseline_medians_us'],r['candidate_medians_us'])]))
 summary={}
 for name,rr in [('all',rows),('active',[r for r in rows if r['active']]),('inactive',[r for r in rows if not r['active']])]:
  if not rr:continue
  s=[r['reduction_percent'] for r in rr];summary[name]=dict(count=len(rr),median=statistics.median(s),min=min(s),max=max(s),both_windows_improve=sum(min(r['windows'])>0 for r in rr))
 print(tag,json.dumps(summary))
 print('worst',json.dumps(sorted([r for r in rows if r['active']],key=lambda r:r['reduction_percent'])[:7]))
 (out/(tag+'_analysis.json')).write_text(json.dumps(dict(summary=summary,rows=rows),indent=2),encoding='utf-8')

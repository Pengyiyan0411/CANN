from pathlib import Path
import json,statistics,sys
path=Path(sys.argv[1]);rows=[json.loads(l) for l in path.read_text().splitlines()]
spec={int(l.split()[0]):list(map(int,l.split())) for l in Path('cases/manifest.txt').read_text().splitlines()}
if Path('cases/extra.txt').exists():spec.update({int(l.split()[0]):list(map(int,l.split())) for l in Path('cases/extra.txt').read_text().splitlines()})
plans={tuple(map(int,l.split(',')[1:3])):list(map(int,l.split(','))) for l in Path('compare.csv').read_text().splitlines()}
res=[]
for i in sorted(set(x['case'] for x in rows)):
 r=[x for x in rows if x['case']==i]
 a=statistics.median(x['device_stream_us_per_call'] for x in r if x['label']=='A')
 b=statistics.median(x['device_stream_us_per_call'] for x in r if x['label']=='B')
 s=spec[i];p=plans.get((s[2],s[3]));changed=p is not None and p[3:7]!=p[7:11]
 old_plan=p[3:7] if p else None;new_plan=p[7:11] if p else None
 if path.name.startswith('r38'):
  old_plan=new_plan
  changed=p is not None and p[8]>=4 and 65536+544+(p[8]+1)*s[2]*4<=192*1024
 res.append(dict(id=i,shape=s[1:],old_plan=old_plan,new_plan=new_plan,changed=changed,baseline_us=a,candidate_us=b,reduction_pct=(1-b/a)*100))
summary={}
for key,rr in [('all',res),('changed',[r for r in res if r['changed']]),('unchanged',[r for r in res if not r['changed']])]:
 if rr:summary[key]=dict(n=len(rr),median_pct=statistics.median(x['reduction_pct'] for x in rr),min_pct=min(x['reduction_pct'] for x in rr),max_pct=max(x['reduction_pct'] for x in rr))
path.with_suffix('.summary.json').write_text(json.dumps(dict(summary=summary,results=res),indent=2))
print(json.dumps(summary,indent=2))
for r in res:print(r)

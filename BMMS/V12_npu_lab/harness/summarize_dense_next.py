from pathlib import Path
import json,statistics
r=Path(__file__).resolve().parent
def events(path,manifest):
 rows=[json.loads(x) for x in path.read_text().splitlines()]
 dims={int(x.split()[0]):list(map(int,x.split()[1:])) for x in manifest.read_text().splitlines()}
 out=[]
 for i in sorted({x['case'] for x in rows}):
  aa=[x['device_stream_us_per_call'] for x in rows if x['case']==i and x['label']=='A'];bb=[x['device_stream_us_per_call'] for x in rows if x['case']==i and x['label']=='B']
  assert len(aa)==len(bb)
  a=statistics.median(aa);b=statistics.median(bb)
  out.append(dict(case=i,dims=dims[i],baseline_us=a,candidate_us=b,reduction_pct=100*(1-b/a),baseline_windows=aa,candidate_windows=bb))
 return dict(cases=out,median_reduction_pct=statistics.median(x['reduction_pct'] for x in out),min_reduction_pct=min(x['reduction_pct'] for x in out),max_reduction_pct=max(x['reduction_pct'] for x in out))
if __name__=='__main__':
 summary={}
 for v,folder in [('r31','cases_c1112_screen'),('r32','cases_shortk')]:
  f=r/f'results/{v}_screen_event.jsonl'
  if not f.exists():continue
  s=events(f,r/f'{folder}/manifest.txt');summary[v]=s
  print(v, {k:x for k,x in s.items() if k!='cases'})
  for x in s['cases']:print(x['case'],x['dims'],round(x['baseline_us'],3),round(x['candidate_us'],3),round(x['reduction_pct'],2))
 (r/'results/dense_next_screen_summary.json').write_text(json.dumps(summary,indent=2)+'\n')

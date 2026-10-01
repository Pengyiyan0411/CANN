from pathlib import Path
import json,statistics,sys,collections
p=Path(sys.argv[1]);rows=[json.loads(x) for x in p.read_text().splitlines() if x.strip()]
groups=collections.defaultdict(lambda:collections.defaultdict(list))
for r in rows:groups[r['case']][r['label']].append(r['device_stream_us_per_call'])
rat=[]; result=[]
for case,g in groups.items():
 a=statistics.median(g['A']);b=statistics.median(g['B']);r=100*(1-b/a);rat.append(r)
 result.append(dict(case=case,baseline_us=a,candidate_us=b,reduction_pct=r))
 print(f'{case:3} {a:8.3f} -> {b:8.3f} {r:7.2f}%')
print('median_pct',statistics.median(rat),'min_pct',min(rat),'max_pct',max(rat))
p.with_suffix('.summary.json').write_text(json.dumps(result,indent=2)+'\n')

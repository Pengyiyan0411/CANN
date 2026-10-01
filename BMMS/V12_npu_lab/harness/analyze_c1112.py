from pathlib import Path
import json,statistics as st
from collections import defaultdict
r=Path(__file__).resolve().parent
for p in sorted((r/'results').glob('c1112*event*.jsonl'))+sorted((r/'results').glob('c1112_nz_screen.jsonl')):
    if not p.stat().st_size:continue
    manifest='cases_c1112_holdout' if 'holdout' in p.stem else 'cases_c1112_screen'
    specs={s['id']:s for s in map(json.loads,(r/manifest/'manifest.jsonl').read_text().splitlines())}
    g=defaultdict(lambda:defaultdict(list));chosen=set()
    for l in p.read_text().splitlines():
        x=json.loads(l);g[x['case']][x['label']].append(x['device_stream_us_per_call'])
        if x['kernel']=='nz':chosen.add(x['case'])
    rows=[]
    for i,v in sorted(g.items()):
        if not v['A'] or not v['B']:continue
        a=st.median(v['A']);b=st.median(v['B']);s=specs[i]
        rows.append(dict(**s,selected=i in chosen,baseline_us=a,candidate_us=b,reduction_pct=100*(1-b/a),windows=min(len(v['A']),len(v['B']))))
    main=[s for s in rows if s['pattern']=='random']
    stat={}
    for tag,sub in [('all',main),('selected',[x for x in main if x['selected']]),('fallback',[x for x in main if not x['selected']]),('c12_selected',[x for x in main if x['selected'] and x['K']<1792]),('c11_selected',[x for x in main if x['selected'] and x['K']>=2048])]:
        if sub:stat[tag]=dict(count=len(sub),median=st.median(s['reduction_pct'] for s in sub),min=min(s['reduction_pct'] for s in sub),max=max(s['reduction_pct'] for s in sub))
    (p.parent/(p.stem+'_summary.json')).write_text(json.dumps(dict(stats=stat,cases=rows),indent=2)+'\n')
    print(p.stem,stat)
    for s in rows:print(s['id'],s['M'],s['N'],s['K'],s['dtype'],s['ta'],s['tb'],round(s['baseline_us'],2),round(s['candidate_us'],2),round(s['reduction_pct'],2),s['windows'])

from pathlib import Path
import json,statistics,sys
r=Path(__file__).resolve().parents[1];o=r/'V12_npu_lab/results/parallel_epilogue_20260929'
tag=sys.argv[1];ver=tag.split('_')[0];ns='bmms12'+ver[1:]
pns={(int(m),int(n)):int(pn) for m,n,pn in [x.split() for x in (r/'V12_npu_lab/narrow_dense/r48_candidates.txt').read_text().splitlines()]}
d=json.loads((o/f'{tag}_summary.json').read_text());active={x['case'][0] for x in d['runs'] if x['version']==ver and any(ns in k for k in x['kernels'])}
rows=[]
for s in d['summary']:
    if s['case'][0] not in active:continue
    z=dict(s,old_pN=pns[tuple(s['case'][2:4])],reduction_pct=100*(1-s['candidate_median_us']/s['baseline_median_us']))
    rows.append(z)
    print(s['case'],z['old_pN'],round(s['baseline_median_us'],3),round(s['candidate_median_us'],3),round(z['reduction_pct'],2))
stats={}
for group in ['all']+sorted(set(x['old_pN'] for x in rows)):
    a=[x for x in rows if group=='all' or x['old_pN']==group];red=[x['reduction_pct'] for x in a]
    stats[str(group)]=dict(configurations=len(a),wins=sum(x>0 for x in red),median_reduction_pct=statistics.median(red),min_reduction_pct=min(red),max_reduction_pct=max(red),both_windows_win=sum(all(t>1 for t in x['speedups']) for x in a))
print(json.dumps(stats,indent=2))
(o/f'{tag}_analysis.json').write_text(json.dumps(dict(stats=stats,rows=rows),indent=2)+'\n')

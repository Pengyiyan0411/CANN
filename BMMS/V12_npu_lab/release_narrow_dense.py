from pathlib import Path
import json,hashlib,statistics,zipfile
root=Path(__file__).resolve().parents[1];out=root/'V12_npu_lab/results/narrow_dense_20260929';e=out/'evidence';versions=root/'BMMS_V12'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=[json.loads(l) for f in ['r37_correctness.jsonl','r37_extra_correctness.jsonl'] for l in (e/'results'/f).read_text().splitlines()]
assert len(rows)==166 and all(x['pass'] for x in rows)
plans={tuple(map(int,l.split(',')[1:3])):list(map(int,l.split(','))) for l in (out/'compare.csv').read_text().splitlines()}
pub=read(e/'results/r37_public_summary.json')['summary'];hit=[r for r in pub if plans[tuple(r['case'][2:4])][3:7]!=plans[tuple(r['case'][2:4])][7:11]]
pg=[100*(1-r['candidate_median_us']/r['baseline_median_us']) for r in hit]
summary=dict(accepted_baseline='v12_baseline_r33.asc',recommended_candidate='v12_r37_dense_singlewave_plan.asc',synthetic_not_hidden=True,
    environment=read(e/'results/environment.json'),precision=dict(configurations=len(rows),calls=sum(r['repeats'] for r in rows),all_pass=True,max_tolerance_ratio=max(r['max_tolerance_ratio'] for r in rows)),
    host_audit=read(out/'audit.json'),r37_event_screen=read(e/'results/r37_screen.summary.json')['summary'],
    r37_event_holdout=read(e/'results/r37_holdout.summary.json')['summary'],r37_aa=read(e/'results/r37_aa.summary.json')['summary'],
    r37_public=dict(configurations=len(pub),changed=len(hit),changed_median_pct=statistics.median(pg),changed_min_pct=min(pg),changed_max_pct=max(pg)),
    r38_incremental_screen=read(e/'results/r38_screen.summary.json')['summary'],r38_incremental_holdout=read(e/'results/r38_holdout.summary.json')['summary'],
    source_sha256={f:sha(versions/f) for f in ['v12_baseline_r33.asc','v12_r37_dense_singlewave_plan.asc','v12_r38_dense_packed_merge.asc']},
    r38_status='research only; small incremental gain, not included in recommended candidate; full public/sanitizer validation not run',
    sanitizer='r37 reuses exact r33 device implementation; no new sanitizer run. Historical r33 race/init reports remain unresolved; numerical checks are not proof of sanitizer cleanliness.')
(out/'SUMMARY.json').write_text(json.dumps(summary,indent=2))
main=read(versions/'MAINLINE.json');assert main['accepted_sota']=='v12_baseline_r33.asc'
for ver,file,status in [('v12_r37','v12_r37_dense_singlewave_plan.asc','recommended pending Judge; 166 configurations x3 precision Pass; independent changed-plan subset median latency reduction 8.57%; r33 remains accepted'),('v12_r38','v12_r38_dense_packed_merge.asc','research only; incremental independent active subset median reduction 0.33%; not recommended this round')]:
 main['candidates']=[c for c in main['candidates'] if c.get('version')!=ver]
 main['candidates'].append(dict(version=ver,file=file,parent='v12_baseline_r33.asc' if ver=='v12_r37' else 'v12_r37_dense_singlewave_plan.asc',sha256=sha(versions/file),status=status,npu_report='../V12_npu_lab/results/narrow_dense_20260929/REPORT.md'))
main['recommended_candidate']='v12_r37_dense_singlewave_plan.asc'
main['next_action']='Submit r37 to Judge and compare all15 with r33, especially11/12. If unchanged, prioritize one calibrated predicate comparing old/new plans before further plan-state probes. r38 remains research only.'
(versions/'MAINLINE.json').write_text(json.dumps(main,ensure_ascii=False,indent=2)+'\n')
for n,status in [(37,main['candidates'][-2]['status']),(38,main['candidates'][-1]['status'])]:
 p=versions/f'v12_r{n}_manifest.json';m=read(p);m['status']=status;m['report']='../V12_npu_lab/results/narrow_dense_20260929/REPORT.md';p.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,indent=2))

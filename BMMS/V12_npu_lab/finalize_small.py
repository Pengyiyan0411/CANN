from pathlib import Path
import hashlib,json,statistics
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V12';out=root/'V12_npu_lab/results/small_20261001'
baseline=v/'v12_baseline_r41.asc';assert hashlib.sha256(baseline.read_bytes()).hexdigest()=='1caf7870ac4154c0f555621ba9c41f4601c6ecee96cb2e8d0bf23acc4fc4f373'
report=json.loads((out/'r72_final_summary.json').read_text());agg=json.loads((out/'r72_final_aggregate.json').read_text())
assert report['source_sha256']['r72']==hashlib.sha256((v/'v12_r72_small_cases_index_padded.asc').read_bytes()).hexdigest()
full=(v/'v12_r72_small_cases_index_padded.asc').read_bytes().decode()
a=full.index('// BMMS1269_BEGIN');b=full.index('// BMMS1269_END',a)+len('// BMMS1269_END')
mod=full[a:b];hook=(root/'V12_npu_lab/small_20261001/r69_hook.txt').read_text()
assert full.replace(mod+'\n\n','',1).replace(hook,'',1)==baseline.read_bytes().decode()
assert mod.encode()==(root/'V12_npu_lab/small_20261001/r72_module.asc').read_bytes()
precision=[]
for name in ('r72_all','r72_fresh','r72_boundary'):
 precision += [json.loads(x) for x in (out/f'{name}.jsonl').read_text().splitlines()]
assert len(precision)==1204 and all(x['pass'] for x in precision)
assert sum(x['repeats'] for x in precision)==3668
san=[]
for p in (out/'san_focus72').glob('*.jsonl'):san += [json.loads(x) for x in p.read_text().splitlines()]
assert len(san)==27 and all(x['pass'] for x in san)
assert not any('ERROR:' in p.read_text() for p in (out/'san_focus72').glob('*.log'))
assert agg['all']['regress_over3pct']==0 and agg['all']['median_reduction_pct']>=5
def hit(c):return c[1]>1 or c[3]%8==0 or c[2]*c[3]<=16
accepted=[s for s in report['summary'] if hit(s['case'])]
stats=dict(precision_configurations=len(precision),precision_calls=sum(x['repeats'] for x in precision),max_tolerance_ratio=max(x['max_tolerance_ratio'] for x in precision),
           profiler_final_configurations=len(report['summary']),all_stats=agg['all'],by_batch=agg['B'],
           new_route_configurations=len(accepted),new_route_median_reduction_pct=statistics.median(100*(1-s['candidate_median_us']/s['baseline_median_us']) for s in accepted),
           new_route_min_reduction_pct=min(100*(1-s['candidate_median_us']/s['baseline_median_us']) for s in accepted),
           sanitizer_checks=27,sanitizer_errors=0,sanitizer_warnings=0,parent_byte_recovery=True,
           sanitizer_scope='Exact extracted r72 new module: 6 B2 full-core configurations x4 tools; B41 loop on block0 x3 tools. Not whole historical source.',
           unresolved_baseline='Old unchanged bmms52 K72 Mul-related sanitizer reports, not root-caused. Not treated as a pass or false positive.',judge15=False)
(out/'FINAL_VALIDATION.json').write_text(json.dumps(stats,indent=2)+'\n')
statuses={68:'Rejected: 860 precision configurations pass; no robust short-dot performance gain.',69:'Superseded: batched gains, but B1 padded-N regressions and index-tail sanitizer errors.',70:'Rejected: 860 precision configurations pass; short-dot median gain 1.71% below acceptance threshold.',71:'Superseded by r72: 1204 precision configurations pass, 7.75% final median gain, but new-path index-tail sanitizer findings.',72:'Ready for user Judge15: final precision and paired performance passed; focused new-module sanitizer checks clean. Baseline remains r41.'}
for n in statuses:
 p=v/f'v12_r{n}_manifest.json';d=json.loads(p.read_text());d['status']=statuses[n]
 if n==72:d['validation']=stats
 p.write_text(json.dumps(d,indent=2)+'\n')
main=json.loads((v/'MAINLINE.json').read_text())
for n in statuses:
 d=json.loads((v/f'v12_r{n}_manifest.json').read_text());matches=list(v.glob(f'v12_r{n}_*.asc'));assert len(matches)==1
 entry=dict(version=f'v12_r{n}',file=matches[0].name,sha256=hashlib.sha256(matches[0].read_bytes()).hexdigest(),parent='v12_baseline_r41.asc',status=statuses[n],npu_report='../V12_npu_lab/results/small_20261001/REPORT.md')
 main['candidates']=[x for x in main['candidates'] if x.get('version')!=entry['version']]+[entry]
main['last_implemented_version']='v12_r72';main['latest_experiment_report']='../V12_npu_lab/results/small_20261001/REPORT.md'
main['latest_experiment_outcome']=f"r72 ready for Judge15. 1204 configurations/3668 calls pass; 168 paired synthetic configurations median time reduction {agg['all']['median_reduction_pct']:.2f}%; no >3% regression. Focused new module sanitizer checks clean; old R52 K72 reports remain unresolved. r41 accepted baseline unchanged."
main['active_candidate']=dict(version='v12_r72',file='v12_r72_small_cases_index_padded.asc',sha256=json.loads((v/'v12_r72_manifest.json').read_text())['sha256'],status='Awaiting user Judge15')
(v/'MAINLINE.json').write_text(json.dumps(main,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(stats,indent=2))

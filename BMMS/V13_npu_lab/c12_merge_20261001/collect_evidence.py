from pathlib import Path
import json,re,statistics,tarfile,hashlib
root=Path(__file__).resolve().parent
def read_jsonl(p):return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
base=read_jsonl(root/'results/precision_r1.jsonl')+read_jsonl(root/'results/precision_remaining_r1.jsonl')
merged=read_jsonl(root/'results/precision_r2.jsonl')+read_jsonl(root/'results/precision_remaining_r2.jsonl')
small=read_jsonl(root/'results/precision_small_r2.jsonl')
assert len(base)==len(merged)==55 and len(small)==38
same_errors=[a['case'] for a,b in zip(base,merged) if a['max_abs_error']==b['max_abs_error']]
def perf(name):
    p=json.loads((root/f'results/{name}_summary.json').read_text())
    vals=[(1-r['candidate_median_us']/r['baseline_median_us'])*100 for r in p['summary']]
    return dict(configurations=len(vals),median_reduction_pct=statistics.median(vals),worst_reduction_pct=min(vals),regress_over3pct=sum(x < -3 for x in vals),summary=p['summary'])
san={}
for group in ('san','san_base'):
    san[group]={}
    for p in sorted((root/group).glob('*.log')):
        if 'launcher' in p.name:continue
        s=p.read_text()
        errors=re.findall(r'^====== ERROR: (.+)$',s,re.M)
        warnings=re.findall(r'^====== WARNING: (.+)$',s,re.M)
        regwarnings=re.findall(r'^\[mssanitizer\] Warning:(.+)$',s,re.M)
        san[group][p.stem]=dict(errors=len(errors),warnings=len(warnings)+len(regwarnings),error_categories=sorted(set(errors)),warning_categories=sorted(set(warnings)),register_warning_count=len(regwarnings))
report=dict(precision=dict(configurations=93,calls=sum(x['repeats'] for x in merged+small),passed=sum(x['pass'] for x in merged+small),failed=[x for x in merged+small if not x['pass']],baseline_failed=[x for x in base if not x['pass']],large_comparison_identical_max_error_cases=len(same_errors),max_tolerance_ratio_pass=max(x['max_tolerance_ratio'] for x in merged+small if x['pass'])),performance=dict(c12=perf('c12_abba'),small=perf('small_abba'),small_confirm=perf('small_confirm')),sanitizer=san)
(root/'results/VALIDATION.json').write_text(json.dumps(report,indent=2)+'\n')
members=[*root.glob('*.asc'),*root.glob('*.py'),root/'CMakeLists.txt',*root.glob('results/*'),*root.glob('san/*'),*root.glob('san_base/*'),*root.glob('cases/*.txt'),*root.glob('cases/*.jsonl'),*root.glob('profiles/**/op_summary*.csv')]
archive=root/'evidence.tar.gz'
with tarfile.open(archive,'w:gz') as tar:
    for p in sorted(set(members)):
        if p.is_file():tar.add(p,arcname=p.relative_to(root))
meta=dict(file=archive.name,bytes=archive.stat().st_size,sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
(root/'evidence_manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
print(json.dumps(dict(precision=report['precision'],sanitizer=san,archive=meta,small_confirm={k:v for k,v in report['performance']['small_confirm'].items() if k!='summary'}),indent=2))

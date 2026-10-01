from pathlib import Path
import json,hashlib,zipfile
root=Path('.').resolve();versions=['r42','r43','r44'];summaries={}
for v in versions:
    records=[]
    for tag in ['correctness','extra_correctness','holdout_correctness']+(['c8_correctness'] if v=='r43' else []):
        p=root/f'results/{v}_{tag}.jsonl'
        if p.exists():records += [json.loads(x) for x in p.read_text().splitlines()]
    summaries[v]=dict(precision_configurations=len(records),precision_calls=sum(x['repeats'] for x in records),all_pass=bool(records) and all(x['pass'] for x in records),max_tolerance_ratio=max((x['max_tolerance_ratio'] for x in records),default=None))
(root/'results/r42_r44_validation_summary.json').write_text(json.dumps(summaries,indent=2))
files=[]
for pattern in ['*.asc','CMakeLists.txt','generate*.py','representatives.json','run_screen.py','check_r42.sh','check_r43.sh','check_r44.sh','finish_r43.sh','archive_r42_r43.py','results/r42*','results/r43*','results/r44*','results/environment.json','logs/r42*','logs/r43*','logs/r44*','cases/*.txt','cases/*.jsonl','san_r43/*']:
    files += [p for p in root.glob(pattern) if p.is_file()]
for v in versions:files+=list(root.glob(f'profiles/{v}_*/PROF_*/mindstudio_profiler_output/op_summary*.csv'))
files=sorted(set(files));manifest=dict(files={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},binary_sha256={v:hashlib.sha256((root/'build'/f'bench_{v}').read_bytes()).hexdigest() for v in ['r41','r42','r43','r44'] if (root/'build'/f'bench_{v}').exists()})
with zipfile.ZipFile(root/'r42_r44_evidence.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in files:z.write(p,p.relative_to(root))
    z.writestr('manifest.json',json.dumps(manifest,indent=2))
print(json.dumps(summaries))

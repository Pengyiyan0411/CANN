from pathlib import Path
import json,hashlib,zipfile
root=Path('.').resolve();versions=['r48','r49','r50'];validation={}
for v in versions:
    tags=['correctness','extra_correctness','holdout_correctness','new_correctness']+(['special_correctness'] if v in ['r49','r50'] else [])
    if v=='r50' and (root/'results/r50_fresh_correctness.jsonl').exists():tags+=['fresh_correctness']
    rows=[json.loads(s) for t in tags for s in (root/f'results/{v}_{t}.jsonl').read_text().splitlines()]
    validation[v]=dict(configurations=len(rows),calls=sum(x['repeats'] for x in rows),all_pass=all(x['pass'] for x in rows),max_tolerance_ratio=max(x['max_tolerance_ratio'] for x in rows))
(root/'results/r48_r50_validation.json').write_text(json.dumps(validation,indent=2))
files=[]
for pattern in ['*.asc','CMakeLists.txt','generate*.py','representatives.json','run_screen.py','*r48*.sh','*r49*.sh','*r50*.sh','r48_candidates.txt','r50_candidates.txt','archive_r48_r50.py','results/r48*','results/r49*','results/r50*','results/environment.json','logs/r48*','logs/r49*','logs/r50*','cases/*.txt','cases/*.jsonl','san_r50/*']:
    files += [p for p in root.glob(pattern) if p.is_file()]
for v in versions:files += list(root.glob(f'profiles/{v}_*/PROF_*/mindstudio_profiler_output/*.csv'))
files+=[root/'finish_epilogue_analysis.sh']
files=sorted(set(files));manifest=dict(files={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},binary_sha256={v:hashlib.sha256((root/'build'/f'bench_{v}').read_bytes()).hexdigest() for v in ['r41']+versions})
with zipfile.ZipFile(root/'r48_r50_evidence.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in files:z.write(p,p.relative_to(root))
    z.writestr('manifest.json',json.dumps(manifest,indent=2))
print(json.dumps(validation))

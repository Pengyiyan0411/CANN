from pathlib import Path
import json,hashlib,zipfile
from summarize_dense_next import events
r=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
s=dict(accepted_baseline='v12_r33',recommended_candidate=None,synthetic_not_hidden=True,
       source_sha256={v:sha(r/f'{v}.asc') for v in ['r33','r34','r35','r36']},
       precision=[],events={},validation_boundary='Screening only: no final public-entry profiler, no sanitizer for rejected candidates; no Judge claims')
for v in ['r34','r35','r36']:
 for p in sorted((r/'results').glob(v+'_*correctness.jsonl')):
  rows=[json.loads(x) for x in p.read_text().splitlines()]
  assert rows and all(x['pass'] for x in rows),p
  s['precision'].append(dict(file=p.name,groups=len(rows),calls=sum(x['repeats'] for x in rows),max_tolerance_ratio=max(x['max_tolerance_ratio'] for x in rows)))
for version,labels in [('r34',['screen']),('r35',['screen','holdout']),('r36',['screen','holdout','guard'])]:
 for label in labels:
  folder='cases_shortk' if version=='r34' else {'screen':'cases_native','holdout':'cases_native_holdout','guard':'cases_native_final'}[label]
  s['events'][f'{version}_{label}']=events(r/f'results/{version}_{label}_event.jsonl',r/f'{folder}/manifest.txt')
(r/'results/native_macro_summary.json').write_text(json.dumps(s,indent=2)+'\n')
files=set()
for v in ['r34','r35','r36']:
 for folder in ['results','logs']:
  for p in (r/folder).glob(v+'_*'):
   if p.is_file():files.add(p)
 for name in [v+'.asc','event_bench_'+v+'.asc','screen_'+v+'.sh']:
  files.add(r/name)
for name in ['r33.asc','main.asc','CMakeLists.txt','summarize_dense_next.py','generate_native.py','generate_native_final.py','generate_shortk.py','check_r36_guard.sh','archive_native_macro.py']:
 files.add(r/name)
for folder in ['cases_native','cases_native_holdout','cases_native_final','cases_shortk']:
 for p in (r/folder).glob('*'):
  if p.suffix in ['.txt','.jsonl']:files.add(p)
for name in ['native_macro_summary.json','native_final_generation.log','native_final_generation_with_env.log']:
 p=r/'results'/name
 if p.exists():files.add(p)
hashes={str(p.relative_to(r)):sha(p) for p in sorted(files)}
with zipfile.ZipFile(r/'results/native_macro_evidence.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(files):z.write(p,str(p.relative_to(r)))
 z.writestr('SHA256.json',json.dumps(hashes,indent=2)+'\n')
for name,x in s['events'].items():print(name,len(x['cases']),x['median_reduction_pct'],x['min_reduction_pct'],x['max_reduction_pct'])
print('precision',s['precision']);print('evidence_files',len(files))

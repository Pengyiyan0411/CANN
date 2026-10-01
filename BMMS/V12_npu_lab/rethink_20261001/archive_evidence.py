from pathlib import Path
import hashlib,json,tarfile
root=Path(__file__).resolve().parent
assert root.joinpath('results/r67.status').read_text().strip()=='R67_DONE'
assert root.joinpath('results/followup.status').read_text().strip()=='FOLLOWUP_DONE'
files=[]
for pat in ['*.asc','*.sh','*.py','CMakeLists.txt','catlass_headers.tar.gz','results/*','logs/*',
            'profiles/PROF_*/mindstudio_profiler_output/op_summary*.csv',
            'profiles/*/PROF_*/mindstudio_profiler_output/op_summary*.csv',
            'cases/*.txt','cases/manifest.jsonl','cases/specs.json']:
 for p in root.glob(pat):
  if p.is_file() and (p.relative_to(root).as_posix(),p.resolve()) not in files:
   files.append((p.relative_to(root).as_posix(),p.resolve()))
extra=Path('/home/developer/bmms_case12_k1_20261001/cases_r59_extra')
for p in extra.glob('*'):
 if p.suffix in ('.txt','.json','.jsonl'):
  files.append(('metadata_extra/'+p.name,p))
records=[dict(path=name,size=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for name,p in files]
manifest=root/'evidence_manifest.json';manifest.write_text(json.dumps(records,indent=2)+'\n')
out=root/'rethink_evidence.tar.gz'
with tarfile.open(out,'w:gz') as t:
 for name,p in files:t.add(p,arcname=name,recursive=False)
 t.add(manifest,arcname='evidence_manifest.json',recursive=False)
print(json.dumps(dict(files=len(files),size=out.stat().st_size,sha256=hashlib.sha256(out.read_bytes()).hexdigest())))

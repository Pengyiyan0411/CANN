"""Source, build, correctness, profiler CSV and input manifest archive for r62+ experiments."""
from pathlib import Path
import tarfile,json,hashlib
root=Path(__file__).resolve().parent
versions=['r41']+[v for v in ('r62','r63','r64') if (root/f'{v}.asc').exists()]
files=set()
for name in ['main.asc','CMakeLists.txt','run_screen.py','generate_cases.py','generate_r59_extra.py','archive_wide.py']+[v+'.asc' for v in versions]:
 if (root/name).exists():files.add(root/name)
for folder in ['cases','cases_r59_extra']:
 files.update(p for p in (root/folder).glob('*') if p.suffix in ('.txt','.json','.jsonl'))
for ver in versions[1:]:
 files.update(p for p in root.glob(f'*{ver}*') if p.is_file())
 for folder in ('logs','results'):
  files.update(p for p in (root/folder).glob(f'{ver}*') if p.is_file() and p.suffix in ('.json','.jsonl','.log','.txt','.status'))
 for p in (root/'profiles').glob(f'{ver}*/PROF_*/mindstudio_profiler_output/*.csv'):files.add(p)
manifest=dict(versions=versions,binary_sha256={v:hashlib.sha256((root/f'build/bench_{v}').read_bytes()).hexdigest() for v in versions if (root/f'build/bench_{v}').exists()},
              files={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)})
mf=root/'results/wide_evidence_manifest.json';mf.write_text(json.dumps(manifest,indent=2)+'\n');files.add(mf)
archive=root/'results/wide_evidence.tar.gz'
with tarfile.open(archive,'w:gz') as tf:
 for p in sorted(files):tf.add(p,arcname=p.relative_to(root).as_posix())
print(json.dumps(dict(file=str(archive),bytes=archive.stat().st_size,sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),files=len(files))))

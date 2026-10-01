"""Archive reproducible source, exact inputs' seeds/hashes, validation and profiler CSV."""
from pathlib import Path
import json,hashlib,tarfile
root=Path(__file__).resolve().parent
files=set()
for name in ['r41.asc','r59.asc','r60.asc','r61.asc','main.asc','CMakeLists.txt','generate_cases.py','run_screen.py',
             'check_r59.sh','check_r60.sh','detail_r59.sh','summarize_r59_detail.py',
             'generate_r59_extra.py','extra_r59_r60.sh','archive_nmajor.py',
             'r59_bootstrap.log','r59_detail_bootstrap.log','r60_bootstrap.log','r60_retry_bootstrap.log',
             'check_r61.sh','r61_bootstrap.log']:
    if (root/name).exists():files.add(root/name)
for directory in ['cases','cases_r59_extra']:
    for p in (root/directory).glob('*'):
        if p.suffix in ('.txt','.json','.jsonl'):files.add(p)
for folder in ('logs','results'):
    for p in (root/folder).glob('r*'):
        if p.is_file() and p.name.startswith(('r59','r60','r61','r41_extra')) and p.suffix in ('.txt','.log','.json','.jsonl','.status'):
            files.add(p)
for p in (root/'profiles').glob('r*_*/PROF_*/mindstudio_profiler_output/*.csv'):
    if p.relative_to(root/'profiles').parts[0].startswith(('r59','r60','r61')):files.add(p)
files.update(p for p in (root/'r60_generation_error').glob('*') if p.is_file())
binary_hashes={v:hashlib.sha256((root/f'build/bench_{v}').read_bytes()).hexdigest() for v in ('r41','r59','r60','r61')}
manifest={'binary_sha256':binary_hashes,'files':{p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}}
mf=root/'results/r59_r61_evidence_manifest.json';mf.write_text(json.dumps(manifest,indent=2)+'\n');files.add(mf)
archive=root/'results/r59_r61_evidence.tar.gz'
with tarfile.open(archive,'w:gz') as tf:
    for p in sorted(files):tf.add(p,arcname=p.relative_to(root).as_posix())
print(json.dumps({'archive':str(archive),'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'files':len(files)}))

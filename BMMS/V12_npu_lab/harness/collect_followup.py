from pathlib import Path
import hashlib
import json
import zipfile

root=Path(__file__).resolve().parent
files=[]
for folder in ['results','logs','mindstudio_sanitizer_log']:
    files.extend(p for p in (root/folder).rglob('*') if p.is_file())
files.extend((root/'profiles').glob('*/PROF_*/mindstudio_profiler_output/*.csv'))
files.extend((root/'profiles/r03_timeline').glob('OPPROF_*/*.csv'))
for folder in ['cases','cases_followup','cases_native','cases_native_holdout']:
    files.extend((root/folder).glob('*.txt'));files.extend((root/folder).glob('*.jsonl'))
files.extend((root/'build/CMakeFiles').glob('*.dir/flags.make'))
hashes={}
for name in ['r03.asc','r06.asc','r07.asc','r08.asc','r09.asc','build/bench_r03','build/bench_r07','build/bench_r08','build/bench_r09','build/event_bench_r07','build/event_bench_r09']:
    p=root/name
    if p.is_file():hashes[name]=hashlib.sha256(p.read_bytes()).hexdigest()
(root/'logs/followup_hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
files.append(root/'logs/followup_hashes.json')
with zipfile.ZipFile(root/'followup_results.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(set(files)):z.write(p,p.relative_to(root).as_posix())
print('Archived',len(set(files)),'files')

from pathlib import Path
import hashlib, json, zipfile
root=Path(__file__).resolve().parent
files=[]
for folder in ['results','logs']:
    files.extend(p for p in (root/folder).glob('*') if p.is_file() and any(k in p.name for k in ['split','r10','r11','r12']))
files.extend((root/'profiles').glob('split*/PROF_*/mindstudio_profiler_output/*.csv'))
for folder in ['cases_split','cases_split_controls','cases','cases_followup']:
    files.extend((root/folder).glob('*.txt'));files.extend((root/folder).glob('*.jsonl'))
hashes={}
for name in ['r03.asc','r10.asc','r11.asc','r12.asc','build/bench_r03','build/bench_r10','build/bench_r11','build/bench_r12',
             'build/event_bench_r10','build/event_bench_r11','build/event_bench_r12',
             'main.asc','event_bench_r10.asc','event_bench_r11.asc','event_bench_r12.asc',
             'generate_split.py','generate_followup.py','run_screen.py','run_split.sh','run_split_r11.sh','run_split_r12.sh']:
    p=root/name
    if p.is_file():hashes[name]=hashlib.sha256(p.read_bytes()).hexdigest()
(root/'logs/split_hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
files.append(root/'logs/split_hashes.json')
for target in ['bench_r03','bench_r10','event_bench_r10','bench_r11','event_bench_r11','bench_r12','event_bench_r12']:
    p=root/f'build/CMakeFiles/{target}.dir/flags.make'
    if p.exists():files.append(p)
with zipfile.ZipFile(root/'split_results.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(set(files)):z.write(p,p.relative_to(root).as_posix())
print('Archived',len(set(files)),'files')

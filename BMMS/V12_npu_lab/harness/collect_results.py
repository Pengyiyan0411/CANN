from pathlib import Path
import zipfile
root=Path(__file__).resolve().parent
items=[]
for name in ['results','logs']:
    items.extend(p for p in (root/name).rglob('*') if p.is_file())
items.extend((root/'profiles').glob('*/PROF_*/mindstudio_profiler_output/*.csv'))
items += [root/'cases/manifest.jsonl',root/'cases/manifest.txt',root/'cases/smoke.txt',root/'cases/profile_full_nn.txt',root/'build/CMakeFiles/bench_r03.dir/flags.make',root/'build/CMakeFiles/bench_r06.dir/flags.make']
with zipfile.ZipFile(root/'session_results.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(set(items)):z.write(p,p.relative_to(root).as_posix())
print('Archived',len(set(items)),'files')

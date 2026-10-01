from pathlib import Path
import hashlib,json,zipfile
r=Path(__file__).resolve().parent;files=set()
for v in [25,26,27]:
 for pattern in [f'results/r{v}_*.*',f'logs/r{v}_*.*',f'profiles/r{v}_*/PROF_*/mindstudio_profiler_output/op_summary*.csv']:
  files.update(r.glob(pattern))
 for name in [f'r{v}.asc',f'event_bench_r{v}.asc',f'screen_r{v}.sh']:
  if (r/name).exists():files.add(r/name)
for name in ['r19.asc','main.asc','CMakeLists.txt','generate_r25_values.py','run_screen.py','analyze_dense_macro.py','validate_dense_winner.sh','archive_dense_macro.py']:
 files.add(r/name)
for name in ['cases','cases_c1112_screen','cases_c1112_holdout','cases_c8_final','cases_split','cases_split_controls','cases_c12_holdout','cases_r25_values']:
 files.update((r/name).glob('*.txt'));files.update((r/name).glob('*.jsonl'))
inventory={str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files) if p.is_file() and p.suffix!='.zip'}
with zipfile.ZipFile(r/'results/dense_macro_evidence.zip','w',zipfile.ZIP_DEFLATED) as z:
 for name in inventory:z.write(r/name,name)
 z.writestr('INVENTORY_SHA256.json',json.dumps(inventory,indent=2)+'\n')
print('ARCHIVED',len(inventory))

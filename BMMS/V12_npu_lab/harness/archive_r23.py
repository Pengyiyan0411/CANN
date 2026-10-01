from pathlib import Path
import hashlib,json,zipfile
r=Path(__file__).resolve().parent
files=set()
for pattern in ['results/r23_*.*','logs/r23_*.*','profiles/r23_signal_*/PROF_*/mindstudio_profiler_output/op_summary*.csv']:
    files.update(r.glob(pattern))
for name in ['r19.asc','r22.asc','r23.asc','main.asc','CMakeLists.txt','check_r23.sh','run_screen.py','archive_r23.py','cases_c1112_holdout/r23_signal.txt']:
    files.add(r/name)
for name in ['cases','cases_c1112_screen','cases_c1112_holdout','cases_c8_final','cases_split','cases_split_controls','cases_c12_holdout']:
    files.add(r/name/'manifest.txt')
inventory={str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files) if p.is_file()}
with zipfile.ZipFile(r/'results/r23_evidence.zip','w',zipfile.ZIP_DEFLATED) as z:
    for name in inventory:z.write(r/name,name)
    z.writestr('INVENTORY_SHA256.json',json.dumps(inventory,indent=2)+'\n')
print('ARCHIVED',len(inventory))

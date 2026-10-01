"""Archive completed Case12 evidence, omitting regenerable tensors and binaries."""
from pathlib import Path
import hashlib,json,zipfile
r=Path(__file__).resolve().parent
items=set()
for pat in ['results/c12*','logs/c12*','profiles/c12*/**/*','cases_c12*/*','cases/*.txt','cases/*.jsonl','cases_c8*/*.txt','cases_c8*/*.jsonl','cases_split/*.txt','cases_split/*.jsonl','cases_split_controls/*.txt','cases_split_controls/*.jsonl','build/CMakeFiles/*r19*/*.make','build/CMakeFiles/*r20*/*.make','build/CMakeFiles/*r21*/*.make']:
    for p in r.glob(pat):
        if p.is_file() and p.suffix.lower() not in {'.bin','.db','.sqlite','.o','.so','.a'}:
            # Profiler raw device traces are regenerable, keep CSV/JSON/log output.
            if str(p.relative_to(r)).startswith('profiles/') and p.suffix.lower() not in {'.csv','.json','.log','.txt','.done'}:continue
            items.add(p)
for pat in ['r19.asc','r20.asc','r21.asc','main.asc','event_c12_plan.asc','event_bench_r20.asc','event_bench_r21.asc','c12_plans.h','*c12*.py','*c12*.sh','generate_cases.py','generate_c8*.py','generate_split*.py','run_screen.py','CMakeLists.txt']:
    items.update(p for p in r.glob(pat) if p.is_file())
inventory=[]
with zipfile.ZipFile(r/'case12_evidence.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(items):
        rel=str(p.relative_to(r));data=p.read_bytes()
        z.writestr(rel,data)
        inventory.append(dict(path=rel,size=len(data),sha256=hashlib.sha256(data).hexdigest()))
    z.writestr('INVENTORY.json',json.dumps(inventory,indent=2)+'\n')
print(json.dumps(dict(files=len(inventory),bytes=sum(x['size'] for x in inventory),archive_bytes=(r/'case12_evidence.zip').stat().st_size)))

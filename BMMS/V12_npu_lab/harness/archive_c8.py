"""Archive completed Case8 evidence, omitting regenerable tensors and binaries."""
from pathlib import Path
import hashlib,json,zipfile
r=Path(__file__).resolve().parent
items=set()
for pat in ['results/c8*','profiles/c8*/**/*','cases_c8*/*','cases_split/*.txt','cases_split/*.jsonl','cases_split_controls/*.txt','cases_split_controls/*.jsonl','build/CMakeFiles/*r1[2-9]*/*.make']:
    for p in r.glob(pat):
        if p.is_file() and p.suffix.lower() not in {'.bin','.db','.sqlite','.o','.so','.a'}:
            # Profiler raw device traces are regenerable, keep CSV/JSON/log output.
            if str(p.relative_to(r)).startswith('profiles/') and p.suffix.lower() not in {'.csv','.json','.log','.txt','.done'}:continue
            items.add(p)
for pat in ['*.asc','*.py','*.sh','CMakeLists.txt']:
    items.update(p for p in r.glob(pat) if p.is_file())
inventory=[]
with zipfile.ZipFile(r/'case8_evidence.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(items):
        rel=str(p.relative_to(r));data=p.read_bytes()
        z.writestr(rel,data)
        inventory.append(dict(path=rel,size=len(data),sha256=hashlib.sha256(data).hexdigest()))
    z.writestr('INVENTORY.json',json.dumps(inventory,indent=2)+'\n')
print(json.dumps(dict(files=len(inventory),bytes=sum(x['size'] for x in inventory),archive_bytes=(r/'case8_evidence.zip').stat().st_size)))

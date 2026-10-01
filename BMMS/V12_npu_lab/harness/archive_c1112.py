from pathlib import Path
import hashlib,json,zipfile
r=Path(__file__).resolve().parent;items=set()
for pat in ['results/c1112*','logs/c1112*','profiles/c1112*/**/*','cases_c1112*/*','cases_c12_holdout/*.txt','cases_c12_holdout/*.jsonl','cases/*.txt','cases/*.jsonl','cases_c8*/*.txt','cases_c8*/*.jsonl','cases_split/*.txt','cases_split/*.jsonl','cases_split_controls/*.txt','cases_split_controls/*.jsonl','build/CMakeFiles/*r19*/*.make','build/CMakeFiles/*r22*/*.make','build/CMakeFiles/event_c1112*/*.make']:
 for p in r.glob(pat):
  if p.is_file() and p.suffix.lower() not in {'.bin','.db','.sqlite','.o','.so','.a'}:
   if str(p.relative_to(r)).startswith('profiles/') and p.suffix.lower() not in {'.csv','.json','.log','.txt','.done'}:continue
   items.add(p)
for pat in ['r19.asc','r22.asc','main.asc','event_c1112_nz.asc','event_bench_r22.asc','*c1112*.py','*c1112*.sh','generate*.py','run_screen.py','CMakeLists.txt']:
 items.update(p for p in r.glob(pat) if p.is_file())
inventory=[]
with zipfile.ZipFile(r/'c1112_evidence.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(items):
  rel=str(p.relative_to(r));data=p.read_bytes();z.writestr(rel,data)
  inventory.append(dict(path=rel,size=len(data),sha256=hashlib.sha256(data).hexdigest()))
 z.writestr('INVENTORY.json',json.dumps(inventory,indent=2)+'\n')
print(json.dumps(dict(files=len(inventory),archive_bytes=(r/'c1112_evidence.zip').stat().st_size)))

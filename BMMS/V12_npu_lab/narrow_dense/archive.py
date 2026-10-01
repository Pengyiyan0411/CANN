from pathlib import Path
import json,hashlib,zipfile
root=Path('.').resolve();files=[]
for pat in ['*.asc','*.py','*.sh','*.hpp','*.csv','*.json','CMakeLists.txt','logs/*','results/*','cases/*.txt','cases/*.jsonl']:
 for p in root.glob(pat):
  if p.is_file() and p.name not in ['evidence_manifest.json','evidence.zip'] and p not in files:files.append(p)
for p in root.glob('profiles/**/op_summary*.csv'):files.append(p)
binary_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'build').iterdir() if p.is_file() and (p.name.startswith('bench_') or p.name.startswith('event_') or p.name.startswith('sanitize_'))}
manifest=dict(files={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)},binary_sha256=binary_hashes,inputs='binary inputs omitted; generator, seeds, tensor SHA256 and FP64 references included')
(root/'evidence_manifest.json').write_text(json.dumps(manifest,indent=2))
with zipfile.ZipFile(root/'evidence.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in files+[root/'evidence_manifest.json']:z.write(p,p.relative_to(root))
with zipfile.ZipFile(root/'evidence.zip') as z:assert z.testzip() is None
print('archived',len(files),'files', (root/'evidence.zip').stat().st_size,'bytes')

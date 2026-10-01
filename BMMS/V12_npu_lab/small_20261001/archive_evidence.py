from pathlib import Path
import tarfile,hashlib,json
root=Path(__file__).resolve().parent
items=set()
for sub in ('results','san_r69','san_focus','san_focus72','san_cases'):
 for p in (root/sub).rglob('*'):
  if p.is_file():items.add(p)
for p in (root/'cases').iterdir():
 if p.is_file() and p.suffix in ('.json','.jsonl','.txt'):items.add(p)
for p in (root/'profiles').rglob('*.csv'):items.add(p)
for p in root.iterdir():
 if p.is_file() and p.suffix in ('.asc','.py','.sh','.txt'):items.add(p)
files=[dict(path=str(p.relative_to(root)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(items)]
(root/'evidence_index.json').write_text(json.dumps(files,indent=2)+'\n')
dest=root/'small_evidence.tar.gz'
with tarfile.open(dest,'w:gz') as tar:
 for p in sorted(items):tar.add(p,arcname=str(p.relative_to(root)))
 tar.add(root/'evidence_index.json',arcname='evidence_index.json')
print(json.dumps(dict(files=len(files),bytes=dest.stat().st_size,sha256=hashlib.sha256(dest.read_bytes()).hexdigest())))

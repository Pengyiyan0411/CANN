from pathlib import Path
import torch,json,hashlib
torch.set_num_threads(2)
root=Path(__file__).resolve().parent;out=root/'cases';rows=[];meta=[]
for dt in (1,2):
 for ta,tb in ((0,0),(0,1),(1,0),(1,1)):
  cid=30900+len(rows);B,M,N,K=41,16,9,112;seed=26102000+cid
  g=torch.Generator().manual_seed(seed);dtype=torch.float16 if dt==1 else torch.bfloat16
  a=(torch.randn(B,M,K,generator=g)*.25).to(dtype);b=(torch.randn(B,K,N,generator=g)*.25).to(dtype)
  gold=(a.double()@b.double()).amax(-1).sum(-1)
  aa=a.transpose(-1,-2).contiguous() if ta else a;bb=b.transpose(-1,-2).contiguous() if tb else b
  hashes={}
  for name,t in [('a',aa.view(torch.int16)),('b',bb.view(torch.int16)),('golden',gold)]:
   raw=t.numpy().tobytes();(out/f'case{cid}_{name}.bin').write_bytes(raw);hashes[name]=hashlib.sha256(raw).hexdigest()
  rows.append(f'{cid} {B} {M} {N} {K} {dt} {ta} {tb}');meta.append(dict(id=cid,seed=seed,B=B,M=M,N=N,K=K,dtype=dt,ta=ta,tb=tb,hashes=hashes))
(out/'boundary.txt').write_text('\n'.join(rows)+'\n');(out/'boundary_meta.json').write_text(json.dumps(meta,indent=2)+'\n')
(out/'sanitize_full.txt').write_text((out/'sanitize.txt').read_text()+'\n'.join(rows)+'\n')
print('BOUNDARY',len(rows),'SANITIZE',len((out/'sanitize_full.txt').read_text().splitlines()))

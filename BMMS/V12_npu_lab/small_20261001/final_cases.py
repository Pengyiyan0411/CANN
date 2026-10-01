from pathlib import Path
import torch,json,hashlib
torch.set_num_threads(2);root=Path(__file__).resolve().parent;out=root/'cases';rows=[];meta=[]
# Frozen after r69 holdout exposed single-batch padded-N regressions, before r71 measurements.
# Distinct shapes/seeds validate the structural acceptance guard, not fitted timing values.
shapes=[(2,4,40),(4,3,88),(5,2,120),(3,8,48),(7,8,104),(9,8,112),(2,16,80),(5,16,96),(16,8,128),(12,16,64),
        (4,9,72),(8,3,96),(10,11,112),(14,7,88)]
for M,N,K in shapes:
 for B in (1,2,64):
  for dt in (1,2):
   for ta,tb in ((0,0),(0,1),(1,0),(1,1)):
    cid=31000+len(rows);seed=27102000+cid;g=torch.Generator().manual_seed(seed);dtype=torch.float16 if dt==1 else torch.bfloat16
    a=(torch.randn(B,M,K,generator=g)*.25).to(dtype);b=(torch.randn(B,K,N,generator=g)*.25).to(dtype)
    gold=(a.double()@b.double()).amax(-1).sum(-1)
    aa=a.transpose(-1,-2).contiguous() if ta else a;bb=b.transpose(-1,-2).contiguous() if tb else b
    hashes={}
    for name,t in [('a',aa.view(torch.int16)),('b',bb.view(torch.int16)),('golden',gold)]:
     raw=t.numpy().tobytes();(out/f'case{cid}_{name}.bin').write_bytes(raw);hashes[name]=hashlib.sha256(raw).hexdigest()
    rows.append(f'{cid} {B} {M} {N} {K} {dt} {ta} {tb}')
    meta.append(dict(id=cid,seed=seed,B=B,M=M,N=N,K=K,dtype=dt,ta=ta,tb=tb,hashes=hashes,r71_hit=(B>1 or N%8==0 or M*N<=16)))
(out/'final_fresh.txt').write_text('\n'.join(rows)+'\n');(out/'final_meta.json').write_text(json.dumps(meta,indent=2)+'\n')
# A balanced performance subset; full final correctness covers all 336 cases.
selected=[r for r,s in zip(rows,meta) if (s['ta'],s['tb']) in ((0,0),(1,1))]
(out/'final_fresh_perf.txt').write_text('\n'.join(selected)+'\n')
print('FINAL_FRESH',len(rows),'PERFORMANCE',len(selected))

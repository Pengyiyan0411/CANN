"""Additional genuine r59/r60 route hits and exact K-cancellation inputs, CPU only."""
from pathlib import Path
import torch,json,hashlib
torch.set_num_threads(4)
root=Path(__file__).resolve().parent;out=root/'cases_r59_extra';out.mkdir(exist_ok=True)
specs=[]
for M,N,ta in [(1344,4928,0),(1344,4928,1),(1392,4928,0),(1408,4928,0),(1408,4928,1),
               (1424,4672,0),(1472,4672,0),(1472,4672,1),(1520,4672,0)]:
    for dt in (1,2):specs.append(dict(id=2000+len(specs),B=1,M=M,N=N,K=1536,dtype=dt,ta=ta,tb=0,pattern='random'))
for dt in (1,2):
    for ta in (0,1):specs.append(dict(id=2000+len(specs),B=1,M=1280,N=4160,K=1536,dtype=dt,ta=ta,tb=0,pattern='exact_K_cancel'))
(out/'specs.json').write_text(json.dumps(specs,indent=2)+'\n')
metadata=[];rows=[]
for s in specs:
    i,M,N,K=s['id'],s['M'],s['N'],s['K'];dt=torch.float16 if s['dtype']==1 else torch.bfloat16
    seed=26105900+i;g=torch.Generator().manual_seed(seed)
    a=(torch.randn(1,M,K,generator=g)*.25).to(dt);b=(torch.randn(1,K,N,generator=g)*.25).to(dt)
    if s['pattern']=='exact_K_cancel':
        aa=(torch.randint(-4,5,(1,M,K//2),generator=g).float()/8).to(dt)
        bb=(torch.randint(-4,5,(1,K//2,N),generator=g).float()/8).to(dt)
        a=torch.cat((aa,aa),dim=2);b=torch.cat((bb,-bb),dim=1)
    gold=(a.double()@b.double()).amax(-1).sum(-1)
    if s['ta']:a=a.transpose(-1,-2).contiguous()
    hashes={}
    for label,t in [('a',a.view(torch.int16)),('b',b.view(torch.int16)),('golden',gold)]:
        raw=t.numpy().tobytes();(out/f'case{i}_{label}.bin').write_bytes(raw);hashes[label]=hashlib.sha256(raw).hexdigest()
    rows.append(' '.join(str(s[k]) for k in ['id','B','M','N','K','dtype','ta','tb']))
    metadata.append(dict(**s,seed=seed,hashes=hashes,golden=gold.tolist()))
    print(i,s['pattern'],flush=True)
(out/'all.txt').write_text('\n'.join(rows)+'\n')
(out/'manifest.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in metadata))
print('EXTRA_GENERATED',len(specs),flush=True)

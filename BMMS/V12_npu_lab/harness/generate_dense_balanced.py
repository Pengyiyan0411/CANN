"""Additional correctness/holdout shapes; all synthetic, not hidden cases."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import torch

p=argparse.ArgumentParser();p.add_argument('--output',default='cases_dense_balanced');args=p.parse_args()
out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
torch.set_num_threads(4)
specs=[]
import random
rng=random.Random(2092811)
shapes=[(1344,3136,1728),(1728,6208,3392)]
for M,N,K in shapes:
 for layout in range(4):
  for dt in [1,2]:
   specs.append(dict(id=len(specs),label='balanced_independent',B=1,M=M,N=N,K=K,dtype=dt,ta=layout//2,tb=layout%2,pattern='random'))
manifest=[];records=[]
for s in specs:
    B,M,N,K=[s[k] for k in ['B','M','N','K']];g=torch.Generator().manual_seed(2092830+s['id'])
    dtype=torch.float16 if s['dtype']==1 else torch.bfloat16
    a=(torch.randn(B,M,K,generator=g)*0.25).to(dtype);b=(torch.randn(B,K,N,generator=g)*0.25).to(dtype)
    if s['pattern']=='zero':a.zero_();b.zero_()
    elif s['pattern']=='negative':a=a.abs();b=-b.abs()
    elif s['pattern']=='wide_scale':
        a=(a.float()*torch.pow(2.,torch.randint(-5,5,a.shape,generator=g))).to(dtype)
        b=(b.float()*torch.pow(2.,torch.randint(-5,5,b.shape,generator=g))).to(dtype)
    elif s['pattern']=='equal_columns':b=b[:,:,:1].expand(B,K,N).contiguous()
    bd=b.double();gold=torch.zeros(B,dtype=torch.float64)
    for row in range(0,M,128):gold+=(a[:,row:row+128,:].double()@bd).amax(dim=-1).sum(dim=-1)
    stored_a=a.transpose(-1,-2).contiguous() if s['ta'] else a
    stored_b=b.transpose(-1,-2).contiguous() if s['tb'] else b
    hashes={}
    for suffix,t in [('a',stored_a.view(torch.int16)),('b',stored_b.view(torch.int16)),('golden',gold)]:
        data=t.numpy().tobytes();(out/f"case{s['id']}_{suffix}.bin").write_bytes(data);hashes[suffix]=hashlib.sha256(data).hexdigest()
    manifest.append(' '.join(str(s[k]) for k in ['id','B','M','N','K','dtype','ta','tb']))
    records.append(dict(**s,seed=2092830+s['id'],hashes=hashes,golden=gold.tolist()))
    print(f"generated {s['id']} {s['label']}",flush=True)
sets={'manifest':range(len(manifest)),'profile':[0,1,2,3,4,5,6,7], 'sanitize':[0,1], 'screen':range(len(manifest))}
for name,ids in sets.items():
    (out/f'{name}.txt').write_text('\n'.join(manifest[i] for i in ids)+'\n')
(out/'manifest.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))

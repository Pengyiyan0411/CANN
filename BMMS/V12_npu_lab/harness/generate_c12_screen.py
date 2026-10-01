"""Additional correctness/holdout shapes; all synthetic, not hidden cases."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import torch

p=argparse.ArgumentParser();p.add_argument('--output',default='cases_c12_screen');args=p.parse_args()
out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
torch.set_num_threads(4)
specs=[]
shapes=[(1024,1024,1536),(1040,2064,1568),(1536,2048,1664),(2048,2048,1792),(3072,1536,1920),(4096,3072,2016),(8192,1040,1632),(1056,8192,1984)]
for j,(M,N,K) in enumerate(shapes):
 for ta,tb in itertools.product([0,1],[0,1]):
  specs.append(dict(id=len(specs),label='c12_plan_screen',B=1,M=M,N=N,K=K,dtype=1+j%2,ta=ta,tb=tb,pattern='random'))
manifest=[];records=[]
for s in specs:
    B,M,N,K=[s[k] for k in ['B','M','N','K']];g=torch.Generator().manual_seed(200928+s['id'])
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
    records.append(dict(**s,seed=200928+s['id'],hashes=hashes,golden=gold.tolist()))
    print(f"generated {s['id']} {s['label']}",flush=True)
sets={'manifest':range(len(manifest)),'profile':[12]}
for name,ids in sets.items():
    (out/f'{name}.txt').write_text('\n'.join(manifest[i] for i in ids)+'\n')
(out/'manifest.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))

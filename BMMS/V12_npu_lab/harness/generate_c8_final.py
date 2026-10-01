"""Additional correctness/holdout shapes; all synthetic, not hidden cases."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import torch

p=argparse.ArgumentParser();p.add_argument('--output',default='cases_c8_final');args=p.parse_args()
out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
torch.set_num_threads(4)
import random
rng=random.Random(180928)
specs=[]
for i in range(40):
    M=rng.randrange(1024,2048);N=rng.randrange(1024,2048);K=rng.randrange(129,160)*8
    # Deliberately cover nearby pitch residues, including preference false.
    if i%5==0:M=(M//64)*64;N=(N//64)*64;K=(K//64)*64+8
    if i%5==1:K=min(1272,(K//64)*64);N=(N//64)*64+1
    if K<=1024:K=1088
    if M%16==0 and N%16==0 and K%32==0:N+=1
    specs.append(dict(id=i,label='c8_final_unseen',B=1,M=M,N=N,K=K,dtype=1+(i//4)%2,ta=(i//2)%2,tb=i%2,pattern='random'))
manifest=[];records=[]
for s in specs:
    B,M,N,K=[s[k] for k in ['B','M','N','K']];g=torch.Generator().manual_seed(1830928+s['id'])
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
    records.append(dict(**s,seed=1830928+s['id'],hashes=hashes,golden=gold.tolist()))
    print(f"generated {s['id']} {s['label']}",flush=True)
sets={'manifest':range(len(manifest))}
for name,ids in sets.items():
    (out/f'{name}.txt').write_text('\n'.join(manifest[i] for i in ids)+'\n')
(out/'manifest.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))

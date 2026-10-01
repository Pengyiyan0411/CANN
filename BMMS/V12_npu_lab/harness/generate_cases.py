"""Synthetic cases; no inference that these are hidden Judge inputs."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import torch

p=argparse.ArgumentParser();p.add_argument('--output',default='cases');args=p.parse_args()
out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
torch.set_num_threads(4)
specs=[]
for label,B,M,N,K in [('tiny',1,8,8,64),('native',4,32,32,128),('macro_full',1,1024,2048,1024),('macro_tail',1,1040,2064,1056)]:
    for dt,ta,tb in itertools.product([1,2],[0,1],[0,1]):
        specs.append(dict(id=len(specs),label=label,B=B,M=M,N=N,K=K,dtype=dt,ta=ta,tb=tb,pattern='random'))
for pattern in ['zero','negative']:
    specs.append(dict(id=len(specs),label='macro_value',B=1,M=1024,N=2048,K=1024,dtype=1,ta=0,tb=0,pattern=pattern))
manifest=[];records=[]
for s in specs:
    B,M,N,K=[s[k] for k in ['B','M','N','K']];g=torch.Generator().manual_seed(260928+s['id'])
    dtype=torch.float16 if s['dtype']==1 else torch.bfloat16
    a=(torch.randn(B,M,K,generator=g)*0.25).to(dtype);b=(torch.randn(B,K,N,generator=g)*0.25).to(dtype)
    if s['pattern']=='zero':a.zero_();b.zero_()
    elif s['pattern']=='negative':a=a.abs();b=-b.abs()
    # Independent FP64 reference from the actual quantized inputs, in row chunks.
    bd=b.double();gold=torch.zeros(B,dtype=torch.float64)
    for row in range(0,M,128):gold+=(a[:,row:row+128,:].double()@bd).amax(dim=-1).sum(dim=-1)
    stored_a=a.transpose(-1,-2).contiguous() if s['ta'] else a
    stored_b=b.transpose(-1,-2).contiguous() if s['tb'] else b
    hashes={}
    for suffix,t in [('a',stored_a.view(torch.int16)),('b',stored_b.view(torch.int16)),('golden',gold)]:
        data=t.numpy().tobytes();(out/f"case{s['id']}_{suffix}.bin").write_bytes(data);hashes[suffix]=hashlib.sha256(data).hexdigest()
    line=' '.join(str(s[k]) for k in ['id','B','M','N','K','dtype','ta','tb']);manifest.append(line)
    records.append(dict(**s,seed=260928+s['id'],hashes=hashes,golden=gold.tolist()))
    print(f"generated {s['id']} {s['label']}",flush=True)
(out/'manifest.txt').write_text('\n'.join(manifest)+'\n')
smoke={0,4,8,12,16,19,20,23}
(out/'smoke.txt').write_text('\n'.join(manifest[i] for i in sorted(smoke))+'\n')
(out/'manifest.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))

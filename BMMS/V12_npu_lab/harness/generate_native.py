"""Native local-sum boundary, scale and value cases, independent seeds."""
import hashlib
import itertools
import json
from pathlib import Path
import torch
import argparse

p=argparse.ArgumentParser();p.add_argument('--output',default='cases_native');p.add_argument('--holdout',action='store_true');args=p.parse_args()
out=Path(args.output);out.mkdir(exist_ok=True);torch.set_num_threads(4)
specs=[]
shapes=[(1296,48),(2064,64),(4112,64),(6144,48)] if args.holdout else [(272,48),(528,64),(4096,48),(8192,64)]
for M,N in shapes:
    for dt,ta,tb in itertools.product([1,2],[0,1],[0,1]):
        specs.append(dict(id=len(specs),B=1,M=M,N=N,K=128,dtype=dt,ta=ta,tb=tb,pattern='random'))
for pattern in ['zero','negative','wide_scale','equal_columns']:
    specs.append(dict(id=len(specs),B=1,M=4112,N=48,K=128,dtype=1,ta=1,tb=1,pattern=pattern))
for B,M,N,K in [(1,256,64,128),(1,528,32,128),(1,528,80,128),(2,528,64,128),(1,528,64,64)]:
    specs.append(dict(id=len(specs),B=B,M=M,N=N,K=K,dtype=1,ta=0,tb=0,pattern='random'))
lines=[];records=[]
for s in specs:
    B,M,N,K=[s[k] for k in ['B','M','N','K']];seed=820928+s['id'];g=torch.Generator().manual_seed(seed)
    dtype=torch.float16 if s['dtype']==1 else torch.bfloat16
    a=(torch.randn(B,M,K,generator=g)*.25).to(dtype);b=(torch.randn(B,K,N,generator=g)*.25).to(dtype)
    if s['pattern']=='zero':a.zero_();b.zero_()
    elif s['pattern']=='negative':a=a.abs();b=-b.abs()
    elif s['pattern']=='wide_scale':
        a=(a.float()*torch.pow(2.,torch.randint(-5,5,a.shape,generator=g))).to(dtype)
        b=(b.float()*torch.pow(2.,torch.randint(-5,5,b.shape,generator=g))).to(dtype)
    elif s['pattern']=='equal_columns':b=b[:,:,:1].expand(B,K,N).contiguous()
    gold=(a.double()@b.double()).amax(-1).sum(-1)
    sa=a.transpose(-1,-2).contiguous() if s['ta'] else a
    sb=b.transpose(-1,-2).contiguous() if s['tb'] else b
    hashes={}
    for suffix,t in [('a',sa.view(torch.int16)),('b',sb.view(torch.int16)),('golden',gold)]:
        data=t.numpy().tobytes();(out/f"case{s['id']}_{suffix}.bin").write_bytes(data);hashes[suffix]=hashlib.sha256(data).hexdigest()
    lines.append(' '.join(str(s[k]) for k in ['id','B','M','N','K','dtype','ta','tb']))
    records.append(dict(**s,seed=seed,hashes=hashes,golden=gold.tolist()))
sets={'manifest':range(len(lines)),'smoke':[0,3,4,7,24,31,33],
      'screen':[16,19,20,23,24,27,28,31],'holdout':[0,3,7,8,11,15]}
if args.holdout:sets['screen']=[0,3,7,8,11,15,16,19,23,24,27,31]
for name,ids in sets.items():(out/f'{name}.txt').write_text('\n'.join(lines[i] for i in ids)+'\n')
(out/'manifest.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
print(f'Generated {len(specs)} native cases')

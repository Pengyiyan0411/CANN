"""Native local-sum boundary, scale and value cases, independent seeds."""
import hashlib
import itertools
import json
from pathlib import Path
import torch
import argparse

p=argparse.ArgumentParser();p.add_argument('--output',default='cases_native_final');p.add_argument('--holdout',action='store_true');args=p.parse_args()
out=Path(args.output);out.mkdir(exist_ok=True);torch.set_num_threads(4)
specs=[]
shapes=[(M,N) for M in [944,2944,5008,7920] for N in [48,64]]
for M,N in shapes:
    for dt,ta,tb in itertools.product([1,2],[0,1],[0,1]):
        specs.append(dict(id=len(specs),B=1,M=M,N=N,K=128,dtype=dt,ta=ta,tb=tb,pattern='random'))
for pattern in ['zero','negative','wide_scale','equal_columns']:
    for dt in [1,2]:
        specs.append(dict(id=len(specs),B=1,M=8176,N=48,K=128,dtype=dt,ta=1,tb=1,pattern=pattern))
lines=[];records=[]
for s in specs:
    B,M,N,K=[s[k] for k in ['B','M','N','K']];seed=2092835+s['id'];g=torch.Generator().manual_seed(seed)
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
sets={'manifest':range(len(lines)), 'screen':[0,7,16,23,32,39,48,55],
      'public':[0,3,4,7,16,18,20,22,25,27,29,31,32,34,36,38,49,51,53,55,56,58,60,62],
      'sanitize':[64,65,66,67]}
for name,ids in sets.items():(out/f'{name}.txt').write_text('\n'.join(lines[i] for i in ids)+'\n')
(out/'manifest.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
print(f'Generated {len(specs)} native cases')

p=Path('cases_native')
(p/'public.txt').write_text('\n'.join(x for x in (p/'manifest.txt').read_text().splitlines() if int(x.split()[0]) in [0,3,4,7,8,11,12,15,16,19,24,27])+'\n')

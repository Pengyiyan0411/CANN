"""Additional correctness/holdout shapes; all synthetic, not hidden cases."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import torch

p=argparse.ArgumentParser();p.add_argument('--output',default='cases_followup');args=p.parse_args()
out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
torch.set_num_threads(4)
specs=[]
for label,B,M,N,K in [
    ('r06_mtail',1,1040,2048,1056),
    ('r06_rect',1,1536,1024,1280),
    ('r06_ktail',1,2048,1024,1504),
    ('r06_wide',1,1024,3072,1184),
    ('native_n48',1,1024,48,128),
    ('native_n64',1,2048,64,128),
    ('split_k',1,32,64,4096),
]:
    for dt,ta,tb in itertools.product([1,2],[0,1],[0,1]):
        specs.append(dict(id=len(specs),label=label,B=B,M=M,N=N,K=K,dtype=dt,ta=ta,tb=tb,pattern='random'))
for pattern in ['zero','negative','wide_scale','equal_columns']:
    specs.append(dict(id=len(specs),label='r06_value',B=1,M=1040,N=1024,K=1056,dtype=1,ta=0,tb=0,pattern=pattern))
for label,B,M,N,K in [('r06_holdout',1,3072,1536,1440),('r06_guard_n',1,1040,2064,1056),
                     ('r06_guard_k',1,1024,2048,1536),('r06_guard_batch',2,1024,1024,1024),
                     ('r03_small_spatial',4,64,128,256),('padded',1,272,520,1056)]:
    specs.append(dict(id=len(specs),label=label,B=B,M=M,N=N,K=K,dtype=1,ta=0,tb=0,pattern='random'))
manifest=[];records=[]
for s in specs:
    B,M,N,K=[s[k] for k in ['B','M','N','K']];g=torch.Generator().manual_seed(720928+s['id'])
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
    records.append(dict(**s,seed=720928+s['id'],hashes=hashes,golden=gold.tolist()))
    print(f"generated {s['id']} {s['label']}",flush=True)
sets={'manifest':range(len(manifest)),'smoke':[0,3,4,7,8,16,24,57],
      'screen_r06':[0,8,16,24], 'holdout_r06':[7,11,20,27,60],
      'screen_native':[32,35,36,39,40,43,44,47], 'screen_split':[48]}
for name,ids in sets.items():
    (out/f'{name}.txt').write_text('\n'.join(manifest[i] for i in ids)+'\n')
(out/'manifest.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))

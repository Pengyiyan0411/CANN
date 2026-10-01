"""Frozen screen/holdout and numerical stress inputs; CPU FP64 reference."""
from pathlib import Path
import hashlib,json,torch
torch.set_num_threads(4)
root=Path(__file__).resolve().parent; out=root/'cases';out.mkdir(exist_ok=True)
specs=[]
def add(M,N,K,dt,ta,tb,split,pattern='random',B=1):
    specs.append(dict(id=1000+len(specs),B=B,M=M,N=N,K=K,dtype=dt,ta=ta,tb=tb,split=split,pattern=pattern))
screen_ns={4096,4160,4480,4800,5120,5440,5760,6080}
for N in range(4096,6144,64):
    for dt in [1,2]:
        for ta in [0,1]:add(1280,N,1536,dt,ta,0,'screen' if N in screen_ns else 'holdout')
for pattern in ['negative','zero','wide_scale','equal_columns','cancel_pairs']:
    for dt in [1,2]:
        for ta in [0,1]:add(1280,4160,1536,dt,ta,0,'values',pattern)
# All intentionally outside the new scope. They verify routing fallbacks, not hidden-case identity.
guards=[(1280,4160,1536,0,1),(1280,4160,1568,0,0),(1280,4160,1600,1,0),
        (1280,4160,1504,0,0),(1280,6144,1536,0,0),(1280,4032,1536,1,0),
        (1296,4160,1536,0,0),(1408,4160,1536,1,0),(1536,2560,2048,1,1),
        (1024,2048,1280,0,0),(256,256,128,0,0),(64,128,64,1,0),
        (32,1024,256,0,1),(512,48,128,0,0),(512,2048,96,0,0),(16,128,2048,0,1)]
for i,(M,N,K,ta,tb) in enumerate(guards):add(M,N,K,1+i%2,ta,tb,'guards')
# Freeze the split before computing inputs or running any NPU experiment.
(out/'specs.json').write_text(json.dumps(specs,indent=2)+'\n')
rows=[];meta=[]
for s in specs:
    i=s['id'];B,M,N,K=[s[k] for k in ['B','M','N','K']];seed=26100100+i
    g=torch.Generator().manual_seed(seed);dt=torch.float16 if s['dtype']==1 else torch.bfloat16
    a=(torch.randn(B,M,K,generator=g)*.25).to(dt);b=(torch.randn(B,K,N,generator=g)*.25).to(dt)
    if s['pattern']=='negative':a=a.abs();b=-b.abs()
    elif s['pattern']=='zero':a.zero_();b.zero_()
    elif s['pattern']=='wide_scale':
        a=(a.float()*torch.pow(2.,torch.randint(-5,5,a.shape,generator=g))).to(dt)
        b=(b.float()*torch.pow(2.,torch.randint(-5,5,b.shape,generator=g))).to(dt)
    elif s['pattern']=='equal_columns':b=b[:,:,:1].expand(B,K,N).contiguous()
    elif s['pattern']=='cancel_pairs':
        a[:,M//2:,:]=-a[:,:M//2,:];b=b[:,:,:1].expand(B,K,N).contiguous()
    gold=(a.double()@b.double()).amax(-1).sum(-1)
    aa=a.transpose(-1,-2).contiguous() if s['ta'] else a
    bb=b.transpose(-1,-2).contiguous() if s['tb'] else b
    hashes={}
    for key,t in [('a',aa.view(torch.int16)),('b',bb.view(torch.int16)),('golden',gold)]:
        raw=t.numpy().tobytes();(out/f'case{i}_{key}.bin').write_bytes(raw);hashes[key]=hashlib.sha256(raw).hexdigest()
    rows.append(' '.join(str(s[k]) for k in ['id','B','M','N','K','dtype','ta','tb']))
    meta.append(dict(**s,seed=seed,hashes=hashes,golden=gold.tolist()));print('generated',i,s['split'],flush=True)
for split in ['all','screen','holdout','values','guards']:
    (out/f'{split}.txt').write_text('\n'.join(row for row,s in zip(rows,specs) if split=='all' or s['split']==split)+'\n')
(out/'manifest.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in meta))
print('GENERATED',len(specs),flush=True)

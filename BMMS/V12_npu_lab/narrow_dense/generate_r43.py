from pathlib import Path
import random,hashlib,json,torch
torch.set_num_threads(4);out=Path('cases');rng=random.Random(290943);specs=[];used=set()
def add(M,N,K,dt,ta,tb,pattern='random',split='screen'):
    specs.append(dict(id=300+len(specs),B=1,M=M,N=N,K=K,dtype=dt,ta=ta,tb=tb,pattern=pattern,split=split))
# Independent random sets frozen before any r43 performance observation.
for split in ['screen','holdout']:
    for j in range(16):
        ta=j%2;tb=(j//2)%2
        while True:
            M=rng.randrange(1024,2048);N=rng.randrange(1024,2048);K=rng.randrange(1032,1280,8)
            mp=(M+15)//16*16;np=(N+15)//16*16;kp=(K+31)//32*32
            if (M,N,K) not in used and (M%16 or N%16 or K%32) and ((ta and mp%64) or ((kp if tb else np)%64)):break
        used.add((M,N,K))
        for dt in [1,2]:add(M,N,K,dt,ta,tb,split=split)
# Padded N must not introduce zero into a negative maximum; true M only in sum.
for pattern in ['zero','negative','wide_scale','equal_columns']:
    for dt in [1,2]:add(1041,1105,1064,dt,0,0,pattern,split='values')
# Smallest and largest legal extents; packed pitch aligned controls; domain boundary.
for j,(M,N,K) in enumerate([(1024,1025,1032),(2047,2047,1272),(1535,1535,1152),(1536,1536,1152),(1023,1105,1064),(1041,1105,1280)]):
    for dt in [1,2]:add(M,N,K,dt,j%2,(j//2)%2,split='edges')
rows=[];meta=[]
for s in specs:
    i=s['id'];M,N,K=[s[x] for x in ['M','N','K']];seed=29094300+i
    gen=torch.Generator().manual_seed(seed);dt=torch.float16 if s['dtype']==1 else torch.bfloat16
    a=(torch.randn(1,M,K,generator=gen)*.25).to(dt);b=(torch.randn(1,K,N,generator=gen)*.25).to(dt)
    if s['pattern']=='zero':a.zero_();b.zero_()
    elif s['pattern']=='negative':a=a.abs();b=-b.abs()
    elif s['pattern']=='wide_scale':
        a=(a.float()*torch.pow(2.,torch.randint(-5,5,a.shape,generator=gen))).to(dt)
        b=(b.float()*torch.pow(2.,torch.randint(-5,5,b.shape,generator=gen))).to(dt)
    elif s['pattern']=='equal_columns':b=b[:,:,:1].expand(1,K,N).contiguous()
    gold=(a.double()@b.double()).amax(-1).sum(-1)
    sa=a.transpose(-1,-2).contiguous() if s['ta'] else a;sb=b.transpose(-1,-2).contiguous() if s['tb'] else b
    hashes={}
    for suffix,t in [('a',sa.view(torch.int16)),('b',sb.view(torch.int16)),('golden',gold)]:
        raw=t.numpy().tobytes();(out/f'case{i}_{suffix}.bin').write_bytes(raw);hashes[suffix]=hashlib.sha256(raw).hexdigest()
    rows.append(' '.join(str(s[k]) for k in ['id','B','M','N','K','dtype','ta','tb']))
    meta.append(dict(**s,seed=seed,hashes=hashes,golden=gold.tolist()));print('generated',i,flush=True)
for split in ['all','screen','holdout','values','edges']:
    selected=[r for r,s in zip(rows,specs) if split=='all' or s['split']==split]
    (out/f'r43_{split}.txt').write_text('\n'.join(selected)+'\n')
(out/'r43_all.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in meta))
print('DONE',len(specs),flush=True)

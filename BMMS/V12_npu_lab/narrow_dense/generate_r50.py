from pathlib import Path
import json,random,torch,hashlib
torch.set_num_threads(4);p=Path('cases');rng=random.Random(290950)
candidates=[tuple(map(int,s.split())) for s in Path('r50_candidates.txt').read_text().splitlines()]
used={(x['M'],x['N']) for name in ['manifest','extra','r41_holdout','r47_all','r48_holdout'] for x in map(json.loads,(p/f'{name}.jsonl').read_text().splitlines())}
specs=[]
def add(M,N,K,dt,ta,tb,pattern,split):specs.append(dict(id=600+len(specs),B=1,M=M,N=N,K=K,dtype=dt,ta=ta,tb=tb,pattern=pattern,split=split))
for j in range(16):
    ta=j%2;tb=(j//2)%2
    choices=[(M,N) for M,N in candidates if (M,N) not in used and (not ta or M%64==0) and (tb or N%64==0)]
    M,N=rng.choice(choices);used.add((M,N));K=rng.choice([1536,1600] if tb else [1536,1568,1600,1632])
    for dt in [1,2]:add(M,N,K,dt,ta,tb,'random','holdout')
for M,N,K,ta,tb in [(1392,5120,1600,0,0),(1408,5040,1600,1,1)]:
    for pattern in ['negative','zero','wide_scale','equal_columns','cancel_pairs']:
        for dt in [1,2]:add(M,N,K,dt,ta,tb,pattern,'values')
rows=[];meta=[]
for s in specs:
    i=s['id'];M,N,K=[s[k] for k in ['M','N','K']];seed=29095000+i
    g=torch.Generator().manual_seed(seed);dt=torch.float16 if s['dtype']==1 else torch.bfloat16
    a=(torch.randn(1,M,K,generator=g)*.25).to(dt);b=(torch.randn(1,K,N,generator=g)*.25).to(dt)
    if s['pattern']=='negative':a=a.abs();b=-b.abs()
    elif s['pattern']=='zero':a.zero_();b.zero_()
    elif s['pattern']=='wide_scale':
        a=(a.float()*torch.pow(2.,torch.randint(-5,5,a.shape,generator=g))).to(dt)
        b=(b.float()*torch.pow(2.,torch.randint(-5,5,b.shape,generator=g))).to(dt)
    elif s['pattern']=='equal_columns':b=b[:,:,:1].expand(1,K,N).contiguous()
    elif s['pattern']=='cancel_pairs':
        a[:,M//2:,:]=-a[:,:M//2,:];b=b[:,:,:1].expand(1,K,N).contiguous()
    gold=(a.double()@b.double()).amax(-1).sum(-1)
    aa=a.transpose(-1,-2).contiguous() if s['ta'] else a;bb=b.transpose(-1,-2).contiguous() if s['tb'] else b
    hashes={}
    for key,t in [('a',aa.view(torch.int16)),('b',bb.view(torch.int16)),('golden',gold)]:
        raw=t.numpy().tobytes();(p/f'case{i}_{key}.bin').write_bytes(raw);hashes[key]=hashlib.sha256(raw).hexdigest()
    rows.append(' '.join(str(s[k]) for k in ['id','B','M','N','K','dtype','ta','tb']));meta.append(dict(**s,seed=seed,hashes=hashes,golden=gold.tolist()));print('generated',i,flush=True)
for split in ['all','holdout','values']:(p/f'r50_{split}.txt').write_text('\n'.join(row for row,s in zip(rows,specs) if split=='all' or s['split']==split)+'\n')
(p/'r50_all.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in meta));print('DONE',len(specs),flush=True)

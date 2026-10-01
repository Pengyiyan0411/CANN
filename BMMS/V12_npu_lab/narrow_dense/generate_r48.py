from pathlib import Path
import json,random,torch,hashlib
torch.set_num_threads(4);p=Path('cases');rng=random.Random(290948)
candidates=[tuple(map(int,s.split())) for s in Path('r48_candidates.txt').read_text().splitlines()]
used={(x['M'],x['N']) for name in ['manifest','extra','r41_holdout','r47_all'] for x in map(json.loads,(p/f'{name}.jsonl').read_text().splitlines())}
specs=[]
for j,pn in enumerate([2,5,20]*5+[2]):
    ta=j%2;tb=(j//2)%2
    choices=[(M,N) for M,N,PN in candidates if PN==pn and (M,N) not in used and (not ta or M%64==0) and (tb or N%64==0)]
    M,N=rng.choice(choices);used.add((M,N));K=rng.choice([1536,1600] if tb else [1536,1568,1600,1632])
    for dt in [1,2]:specs.append(dict(id=500+len(specs),B=1,M=M,N=N,K=K,dtype=dt,ta=ta,tb=tb,old_pN=pn,split='holdout'))
rows=[];meta=[]
for s in specs:
    i=s['id'];M,N,K=[s[k] for k in ['M','N','K']];seed=29094800+i
    g=torch.Generator().manual_seed(seed);dt=torch.float16 if s['dtype']==1 else torch.bfloat16
    a=(torch.randn(1,M,K,generator=g)*.25).to(dt);b=(torch.randn(1,K,N,generator=g)*.25).to(dt)
    gold=(a.double()@b.double()).amax(-1).sum(-1)
    aa=a.transpose(-1,-2).contiguous() if s['ta'] else a;bb=b.transpose(-1,-2).contiguous() if s['tb'] else b
    hashes={}
    for key,t in [('a',aa.view(torch.int16)),('b',bb.view(torch.int16)),('golden',gold)]:
        raw=t.numpy().tobytes();(p/f'case{i}_{key}.bin').write_bytes(raw);hashes[key]=hashlib.sha256(raw).hexdigest()
    rows.append(' '.join(str(s[k]) for k in ['id','B','M','N','K','dtype','ta','tb']));meta.append(dict(**s,seed=seed,hashes=hashes,golden=gold.tolist()));print('generated',i,flush=True)
(p/'r48_holdout.txt').write_text('\n'.join(rows)+'\n')
(p/'r48_holdout.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in meta));print('DONE',len(specs),flush=True)

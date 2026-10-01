from pathlib import Path
import json,random,hashlib,torch
torch.set_num_threads(4)
out=Path('cases');rng=random.Random(290941)
old=[]
for f in ['manifest.jsonl','extra.jsonl']:
 old += [json.loads(s) for s in (out/f).read_text().splitlines()]
used={(s['M'],s['N'],s['K']) for s in old};specs=[]
for c in [11,12]:
 for j in range(16):
  while True:
   M=rng.randrange(1536 if c==11 else 1280,1792 if c==11 else 1536,16)
   N=rng.randrange(2048 if c==11 else 4096,3072 if c==11 else 6144,16)
   K=rng.randrange(2048 if c==11 else 1536,2560 if c==11 else 1664,32)
   ta=j%2;tb=(j//2)%2
   if ta:M=M//64*64
   if tb:K=K//64*64
   else:N=N//64*64
   if (M,N,K) not in used:break
  used.add((M,N,K))
  for dtype in [1,2]:specs.append(dict(B=1,M=M,N=N,K=K,dtype=dtype,ta=ta,tb=tb,pattern='random',family=c))
rows=[];meta=[]
for offset,s in enumerate(specs):
 i=200+offset;seed=29094100+i;s['id']=i;B,M,N,K=[s[x] for x in ['B','M','N','K']]
 g=torch.Generator().manual_seed(seed);dt=torch.float16 if s['dtype']==1 else torch.bfloat16
 a=(torch.randn(B,M,K,generator=g)*.25).to(dt);b=(torch.randn(B,K,N,generator=g)*.25).to(dt)
 gold=(a.double()@b.double()).amax(-1).sum(-1)
 sa=a.transpose(-1,-2).contiguous() if s['ta'] else a;sb=b.transpose(-1,-2).contiguous() if s['tb'] else b
 hashes={}
 for suffix,t in [('a',sa.view(torch.int16)),('b',sb.view(torch.int16)),('golden',gold)]:
  data=t.numpy().tobytes();(out/f'case{i}_{suffix}.bin').write_bytes(data);hashes[suffix]=hashlib.sha256(data).hexdigest()
 rows.append(' '.join(str(s[k]) for k in ['id','B','M','N','K','dtype','ta','tb']));meta.append(dict(**s,seed=seed,hashes=hashes,golden=gold.tolist()))
 print('generated',i,flush=True)
(out/'r41_holdout.txt').write_text('\n'.join(rows)+'\n');(out/'r41_holdout.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in meta))
print('DONE',len(rows),flush=True)

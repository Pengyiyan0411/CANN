from pathlib import Path
import torch,json,hashlib,itertools,random
torch.set_num_threads(4)
out=Path('cases');out.mkdir(exist_ok=True)
reps=json.loads(Path('representatives.json').read_text())
specs=[];sets={}
def add(B,M,N,K,dt,ta,tb,pattern='random'):
 i=len(specs);specs.append(dict(id=i,B=B,M=M,N=N,K=K,dtype=dt,ta=ta,tb=tb,pattern=pattern));return i
sets['screen']=[]
for j,r in enumerate(reps):
 c,M,N=r[:3]
 for dt in [1,2]:
  ta=(j+dt)%2;tb=(j//2+dt)%2
  sets['screen'].append(add(1,M,N,2176 if c==11 else 1600,dt,ta,tb))
# Fresh independent geometries/seeds, deliberately including tail extents.
sets['holdout']=[];rng=random.Random(290937)
for c in [11,12]:
 for j in range(24):
  M=rng.randrange(1536 if c==11 else 1280,1792 if c==11 else 1536,16)
  N=rng.randrange(2048 if c==11 else 4096,3072 if c==11 else 6144,16)
  K=rng.choice(list(range(2048,2560,32)) if c==11 else [1536,1568,1600,1632])
  ta=j%2;tb=(j//2)%2
  # Keep physical pitches within the confirmed r30 route, not just shape bounds.
  if ta:M=(M//64)*64
  if tb:K=(K//64)*64
  else:N=(N//64)*64
  sets['holdout'].append(add(1,M,N,K,1+j%2,ta,tb))
sets['values']=[]
for pattern,dt in itertools.product(['zero','negative','wide_scale','equal_columns'],[1,2]):
 sets['values'].append(add(1,1392,5616,1600,dt,0,1,pattern))
sets['controls']=[]
for spec in [(1,1,1,64,1,0,0),(1,8,8,64,2,1,1),(4,32,32,128,1,0,1),
             (1,1041,1105,1064,1,0,0),(1,1041,1105,1064,2,1,1),(1,32,64,4096,1,0,0),
             (1,48,80,6112,2,1,1),(1,4112,48,128,1,1,1),(1,2048,4096,1536,1,0,0),
             (1,1024,2048,1024,1,0,0),(1,1536,4096,1280,2,0,0),
             (1,1392,5616,1568,1,1,0)]:sets['controls'].append(add(*spec))
rows=[];meta=[]
for s in specs:
 i=s['id'];B,M,N,K=[s[x] for x in ['B','M','N','K']];seed=29093700+i
 g=torch.Generator().manual_seed(seed);dtype=torch.float16 if s['dtype']==1 else torch.bfloat16
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
  data=t.numpy().tobytes();(out/f'case{i}_{suffix}.bin').write_bytes(data);hashes[suffix]=hashlib.sha256(data).hexdigest()
 rows.append(' '.join(str(s[k]) for k in ['id','B','M','N','K','dtype','ta','tb']))
 meta.append(dict(**s,seed=seed,hashes=hashes,golden=gold.tolist()))
 print('generated',i,flush=True)
sets['manifest']=range(len(rows));sets['aa']=sets['screen'][::6]
sets['public']=sets['screen'][::2]+sets['holdout'][::4]
for key,ids in sets.items():(out/f'{key}.txt').write_text('\n'.join(rows[i] for i in ids)+'\n')
(out/'manifest.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in meta))
print('DONE',len(rows),flush=True)

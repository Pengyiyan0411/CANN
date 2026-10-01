from pathlib import Path
import torch,json,hashlib
torch.set_num_threads(4);out=Path('cases')
specs=[json.loads(l) for l in (out/'manifest.jsonl').read_text().splitlines()]
extra=[]
for s in specs:
 if 34<=s['id']<82 or s['id']>=90:
  t={k:s[k] for k in ['B','M','N','K','dtype','ta','tb','pattern']};t['dtype']=3-t['dtype'];extra.append(t)
for dt in [1,2]:
 for tb in [0,1]:extra.append(dict(B=1,M=1520,N=5120,K=1600,dtype=dt,ta=0,tb=tb,pattern='negative'))
rows=[];records=[]
for offset,s in enumerate(extra):
 i=102+offset;s['id']=i;B,M,N,K=[s[x] for x in ['B','M','N','K']];seed=29093800+i
 g=torch.Generator().manual_seed(seed);dtype=torch.float16 if s['dtype']==1 else torch.bfloat16
 a=(torch.randn(B,M,K,generator=g)*.25).to(dtype);b=(torch.randn(B,K,N,generator=g)*.25).to(dtype)
 if s['pattern']=='negative':a=a.abs();b=-b.abs()
 gold=(a.double()@b.double()).amax(-1).sum(-1)
 sa=a.transpose(-1,-2).contiguous() if s['ta'] else a
 sb=b.transpose(-1,-2).contiguous() if s['tb'] else b
 hashes={}
 for suffix,t in [('a',sa.view(torch.int16)),('b',sb.view(torch.int16)),('golden',gold)]:
  data=t.numpy().tobytes();(out/f'case{i}_{suffix}.bin').write_bytes(data);hashes[suffix]=hashlib.sha256(data).hexdigest()
 rows.append(' '.join(str(s[k]) for k in ['id','B','M','N','K','dtype','ta','tb']))
 records.append(dict(**s,seed=seed,hashes=hashes,golden=gold.tolist()))
(out/'extra.txt').write_text('\n'.join(rows)+'\n');(out/'extra.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in records))
(out/'memory_edge.txt').write_text('\n'.join(rows[-4:])+'\n')
print('Generated',len(extra),'extra dtype/buffer cases')

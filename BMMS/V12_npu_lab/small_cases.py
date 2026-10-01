from pathlib import Path
import hashlib,json,torch
torch.set_num_threads(2)
root=Path(__file__).resolve().parent;out=root/'cases';out.mkdir(exist_ok=True)
specs=[]
def add(B,M,N,K,dt,ta,tb,split,pattern='random'):
 specs.append(dict(id=30000+len(specs),B=B,M=M,N=N,K=K,dtype=dt,ta=ta,tb=tb,split=split,pattern=pattern))
for K in range(32,129,8):
 for dt in (1,2):
  for ta,tb in ((0,0),(0,1),(1,0),(1,1)):
   add(1,1,1,K,dt,ta,tb,'dot_screen' if (ta,tb)==(0,0) else 'dot_holdout')
for pattern in ('negative','zero','wide_scale','k_cancel','alternating'):
 for K in range(32,129,8):
  for dt in (1,2):add(1,1,1,K,dt,0,0,'dot_values',pattern)
shapes=[(2,2,32),(3,5,40),(4,4,64),(4,8,128),(8,8,64),(8,16,128),(16,8,128),(16,16,64)]
for M,N,K in shapes:
 for B in (1,4,32):
  for dt in (1,2):
   for ta,tb in ((0,0),(0,1),(1,0),(1,1)):add(B,M,N,K,dt,ta,tb,'micro_screen')
hs=[(2,7,48),(3,3,56),(5,11,72),(7,9,80),(9,7,88),(11,3,96),(13,5,104),(15,9,112),(16,7,120),(6,16,128)]
for i,(M,N,K) in enumerate(hs):
 for B in (1,17,41,64):
  for dt in (1,2):
   for ta,tb in ((0,0),(0,1),(1,0),(1,1)):add(B,M,N,K,dt,ta,tb,'micro_holdout')
for pattern in ('negative','zero','wide_scale','equal_columns','cancel_pairs','k_cancel'):
 for B in (1,41):
  for dt in (1,2):
   for ta,tb in ((0,0),(0,1),(1,0),(1,1)):add(B,8,9,112,dt,ta,tb,'micro_values',pattern)
for B,M,N,K in [(2,1,1,64),(1,1,1,136),(1,16,16,128),(8,16,16,128),(1,32,16,64),(4,16,32,128),(1,8,8,136),(1,1,8,64),(1,8,1,64)]:
 for dt in (1,2):add(B,M,N,K,dt,0,0,'guards')
(out/'specs.json').write_text(json.dumps(specs,indent=2)+'\n')
rows=[];metadata=[]
for s in specs:
 B,M,N,K=[s[k] for k in ('B','M','N','K')];dt=torch.float16 if s['dtype']==1 else torch.bfloat16
 seed=26102000+s['id'];g=torch.Generator().manual_seed(seed)
 a=(torch.randn(B,M,K,generator=g)*.25).to(dt);b=(torch.randn(B,K,N,generator=g)*.25).to(dt)
 pat=s['pattern']
 if pat=='negative':a=a.abs();b=-b.abs()
 elif pat=='zero':a.zero_();b.zero_()
 elif pat=='wide_scale':
  a=(a.float()*torch.pow(2.,torch.randint(-5,5,a.shape,generator=g))).to(dt)
  b=(b.float()*torch.pow(2.,torch.randint(-5,5,b.shape,generator=g))).to(dt)
 elif pat=='equal_columns':b=b[:,:,:1].expand(B,K,N).contiguous()
 elif pat=='cancel_pairs':
  a[:,M//2:,:]=-a[:,:M//2,:];b=b[:,:,:1].expand(B,K,N).contiguous()
 elif pat=='k_cancel':a[:,:,K//2:]=a[:,:,:K//2];b[:,K//2:,:]=-b[:,:K//2,:]
 elif pat=='alternating':a=a.abs();b=b.abs();b[:,::2,:]=-b[:,::2,:]
 gold=(a.double()@b.double()).amax(-1).sum(-1)
 aa=a.transpose(-1,-2).contiguous() if s['ta'] else a
 bb=b.transpose(-1,-2).contiguous() if s['tb'] else b
 hashes={}
 for name,t in [('a',aa.view(torch.int16)),('b',bb.view(torch.int16)),('golden',gold)]:
  raw=t.numpy().tobytes();(out/f"case{s['id']}_{name}.bin").write_bytes(raw);hashes[name]=hashlib.sha256(raw).hexdigest()
 rows.append(' '.join(str(s[k]) for k in ('id','B','M','N','K','dtype','ta','tb')))
 metadata.append(dict(**s,seed=seed,hashes=hashes,golden=gold.tolist()))
for split in ('all','dot_screen','dot_holdout','dot_values','micro_screen','micro_holdout','micro_values','guards'):
 (out/f'{split}.txt').write_text('\n'.join(r for r,s in zip(rows,specs) if split=='all' or s['split']==split)+'\n')
# A small fixed first screen includes B1/B4/B32, both reduction families and all layouts.
ss=[r for r,s in zip(rows,specs) if s['split']=='micro_screen' and s['dtype']==1 and (s['M'],s['N'],s['K']) in [(2,2,32),(4,4,64),(8,8,64),(8,16,128)] and s['B'] in (1,32)]
(out/'micro_first32.txt').write_text('\n'.join(ss)+'\n');assert len(ss)==32
(out/'dot_smoke.txt').write_text('\n'.join(r for r,s in zip(rows,specs) if s['split']=='dot_screen' and s['K'] in (32,72,128))+'\n')
(out/'micro_smoke.txt').write_text('\n'.join(ss[:4]+ss[-4:])+'\n')
(out/'manifest.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in metadata))
print('GENERATED',len(specs),'cases')

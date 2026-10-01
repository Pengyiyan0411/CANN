from pathlib import Path
import hashlib,json,torch
torch.set_num_threads(4)
root=Path('cases_shortk');root.mkdir(exist_ok=True)
shapes=[(1024,2048,1024),(1536,4096,1280),(3072,2048,1152),(4096,3072,1472),
        (1088,2112,1088),(1728,3136,1344),(2112,5184,1504),(4160,1088,1184),(8192,1024,1024),(1040,2064,1056)]
lines=[];records=[]
for si,(M,N,K) in enumerate(shapes):
 for layout in range(4):
  for dt in [1,2]:
   i=len(lines);ta=layout//2;tb=layout%2;g=torch.Generator().manual_seed(2092900+i)
   dtype=torch.float16 if dt==1 else torch.bfloat16
   a=(torch.randn(1,M,K,generator=g)*.25).to(dtype);b=(torch.randn(1,K,N,generator=g)*.25).to(dtype)
   pattern='random'
   if si==9:
    pattern=['negative','zero','wide_scale','equal_columns'][layout]
    if pattern=='negative':a=a.abs();b=-b.abs()
    elif pattern=='zero':a.zero_();b.zero_()
    elif pattern=='wide_scale':
     a=(a.float()*torch.pow(2.,torch.randint(-5,5,a.shape,generator=g))).to(dtype)
     b=(b.float()*torch.pow(2.,torch.randint(-5,5,b.shape,generator=g))).to(dtype)
    else:b=b[:,:,:1].expand(1,K,N).contiguous()
   bd=b.double();gold=torch.zeros(1,dtype=torch.float64)
   for row in range(0,M,128):gold+=(a[:,row:row+128].double()@bd).amax(dim=-1).sum(dim=-1)
   aa=a.transpose(-1,-2).contiguous() if ta else a
   bb=b.transpose(-1,-2).contiguous() if tb else b
   hashes={}
   for label,t in [('a',aa.view(torch.int16)),('b',bb.view(torch.int16)),('golden',gold)]:
    data=t.numpy().tobytes();(root/f'case{i}_{label}.bin').write_bytes(data);hashes[label]=hashlib.sha256(data).hexdigest()
   lines.append(f'{i} 1 {M} {N} {K} {dt} {ta} {tb}')
   aligned=(not ta or M%64==0) and (K if tb else N)%64==0
   records.append(dict(id=i,M=M,N=N,K=K,dtype=dt,ta=ta,tb=tb,aligned=aligned,pattern=pattern,golden=gold.tolist(),hashes=hashes))
   print('generated',i,M,N,K,flush=True)
sets={'manifest':list(range(80)),'screen':list(range(32)),
      'holdout':[s['id'] for s in records if s['id']>=32 and s['aligned']],
      'public':[0,2,4,6,8,10,12,14,24,26,28,30,32,42,52,62,64,66,68,70,72,74,76,78],
      'sanitize':[0,1,64,65]}
for name,ids in sets.items():(root/f'{name}.txt').write_text('\n'.join(lines[i] for i in ids)+'\n')
(root/'manifest.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in records))

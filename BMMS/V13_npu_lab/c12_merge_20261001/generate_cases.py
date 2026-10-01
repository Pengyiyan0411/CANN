from pathlib import Path
import torch, json, hashlib
torch.set_num_threads(4)
root=Path(__file__).resolve().parent; out=root/'cases'; out.mkdir(exist_ok=True)
spec=[]
def add(B=1,M=1280,N=4096,K=1536,dt=2,ta=1,tb=0,pattern='random',kind='target'):
    spec.append(dict(id=40000+len(spec),B=B,M=M,N=N,K=K,dtype=dt,ta=ta,tb=tb,pattern=pattern,kind=kind))
# Every possible aligned N in the inherited route; includes all former NBIT1 HITs.
for N in range(4096,6144,64):add(N=N)
for pat in ('negative','zero','wide_scale','equal_columns','row_cancel','k_cancel','alternating'):
    add(pattern=pat,kind='values')
for N in (4160,6080): add(N=N,pattern='negative',kind='values')
for kw in [dict(M=1264),dict(M=1296),dict(N=4032),dict(N=4112),dict(N=6144),dict(K=1504),dict(K=1568),dict(B=2),dict(dt=1),dict(ta=0),dict(tb=1)]:
    add(**kw,kind='guard')
for kw in [dict(M=1664,N=2560,K=2304),dict(M=1024,N=2048,K=1024),dict(M=1280,N=3072,K=1280)]:
    add(**kw,kind='dense_control')
rows=[];records=[]
for s in spec:
    B,M,N,K=[s[k] for k in ('B','M','N','K')];dtype=torch.float16 if s['dtype']==1 else torch.bfloat16
    seed=20261001+s['id'];g=torch.Generator().manual_seed(seed)
    a=(torch.randn(B,M,K,generator=g)*.25).to(dtype);b=(torch.randn(B,K,N,generator=g)*.25).to(dtype)
    pat=s['pattern']
    if pat=='negative': a=a.abs();b=-b.abs()
    elif pat=='zero': a.zero_();b.zero_()
    elif pat=='equal_columns': b=b[:,:,:1].expand(B,K,N).contiguous()
    elif pat=='row_cancel':
        a[:,M//2:,:]=-a[:,:M//2,:];b=b[:,:,:1].expand(B,K,N).contiguous()
    elif pat=='k_cancel': a[:,:,K//2:]=a[:,:,:K//2];b[:,K//2:,:]=-b[:,:K//2,:]
    elif pat=='alternating': a=a.abs();b=b.abs();b[:,::2,:]=-b[:,::2,:]
    elif pat=='wide_scale':
        a=(a.float()*torch.pow(2.,torch.randint(-5,5,a.shape,generator=g))).to(dtype)
        b=(b.float()*torch.pow(2.,torch.randint(-5,5,b.shape,generator=g))).to(dtype)
    # FP64 oracle uses actual quantized input, independent from NPU accumulation.
    golden=(a.double()@b.double()).amax(-1).sum(-1)
    aa=a.transpose(-1,-2).contiguous() if s['ta'] else a
    bb=b.transpose(-1,-2).contiguous() if s['tb'] else b
    hashes={}
    for name,t in [('a',aa.view(torch.int16)),('b',bb.view(torch.int16)),('golden',golden)]:
        raw=t.numpy().tobytes();(out/f"case{s['id']}_{name}.bin").write_bytes(raw);hashes[name]=hashlib.sha256(raw).hexdigest()
    rows.append(' '.join(str(s[k]) for k in ('id','B','M','N','K','dtype','ta','tb')))
    records.append(dict(**s,seed=seed,golden=golden.tolist(),sha256=hashes))
    print('Generated',s['id'],pat,flush=True)
for kind in ('all','target','values','guard','dense_control'):
    (out/f'{kind}.txt').write_text('\n'.join(r for r,s in zip(rows,spec) if kind=='all' or s['kind']==kind)+'\n')
perfN=(4096,4160,4224,4352,4608,5120,6080)
perf=[r for r,s in zip(rows,spec) if s['kind']=='target' and s['N'] in perfN or s['kind']=='dense_control']
(out/'perf.txt').write_text('\n'.join(perf)+'\n')
(out/'san_exact.txt').write_text(rows[0]+'\n');(out/'san_tail.txt').write_text(rows[1]+'\n')
(out/'manifest.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in records))
# Reuse previously validated small tensors by symlink. No NPU needed for generation.
old=Path('/home/developer/bmms_small_20261001/cases')
smallrows=(old/'micro_first32.txt').read_text().splitlines()+(old/'dot_smoke.txt').read_text().splitlines()
for row in smallrows:
    cid=int(row.split()[0])
    for name in ('a','b','golden'):
        path=out/f'case{cid}_{name}.bin'
        if not path.exists():path.symlink_to(old/path.name)
(out/'small_regression.txt').write_text('\n'.join(smallrows)+'\n')
print('COMPLETE',len(spec),len(smallrows),flush=True)

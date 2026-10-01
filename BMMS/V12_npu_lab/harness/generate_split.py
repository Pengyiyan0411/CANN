"""Synthetic Case15 cluster, not recovered competition inputs."""
from pathlib import Path
import itertools

# Reuse the audited input quantization / independent float64 oracle.
src=Path('generate_followup.py').read_text()
a=src.index('specs=[]');b=src.index('manifest=[];records=[]')
spec='''specs=[]
screen_shapes=[(16,16,4096),(32,64,4096),(64,64,4096),(32,128,4096),
               (48,80,6112),(16,112,8160),(48,48,4128),(64,48,8192)]
for M,N,K in screen_shapes:
    for dt,ta,tb in itertools.product([1,2],[0,1],[0,1]):
        specs.append(dict(id=len(specs),label='split_screen',B=1,M=M,N=N,K=K,dtype=dt,ta=ta,tb=tb,pattern='random'))
for M,N in itertools.product(range(16,65,16),range(16,129,16)):
    if M*N>4096:continue
    for K in [5152,7136]:
        i=len(specs)
        specs.append(dict(id=i,label='split_holdout',B=1,M=M,N=N,K=K,dtype=1+(i%2),ta=(i//2)%2,tb=(i//4)%2,pattern='random'))
for dt,pattern in itertools.product([1,2],['zero','negative','wide_scale','equal_columns']):
    specs.append(dict(id=len(specs),label='split_values',B=1,M=48,N=80,K=8160,dtype=dt,ta=1,tb=1,pattern=pattern))
for B,M,N,K in [(2,32,64,4096),(1,80,64,4096),(1,32,144,4096),(1,64,80,4096),(1,32,64,4064),(1,32,64,256)]:
    specs.append(dict(id=len(specs),label='split_guard_out',B=B,M=M,N=N,K=K,dtype=1,ta=0,tb=0,pattern='random'))
'''
src=src[:a]+spec+src[b:]
src=src.replace("default='cases_followup'","default='cases_split'").replace('720928','930928')
a=src.index('sets={');b=src.index('for name,ids in sets.items():',a)
src=src[:a]+'''sets={'manifest':range(len(manifest)),
      'screen':[0,8,16,24,32,40,48,56],
      'holdout':[s['id'] for s in specs if s['label']=='split_holdout'],
      'layouts':[3,7,11,15,27,31,35,39,43,47,51,55,59,63],
      'guard':[s['id'] for s in specs if s['label']=='split_guard_out'],
      'sanitize':[35,59], 'profile':[8]}
'''+src[b:]
exec(compile(src,'generate_split_expanded.py','exec'))

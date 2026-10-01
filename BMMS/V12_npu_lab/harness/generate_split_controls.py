"""Representative unaffected routes; never label these as the hidden 15 cases."""
from pathlib import Path
src=Path('generate_followup.py').read_text()
a=src.index('specs=[]');b=src.index('manifest=[];records=[]')
src=src[:a]+'''specs=[]
for label,B,M,N,K,dt,ta,tb in [
    ('dot',1,1,1,64,1,0,0),('dot',1,1,1,88,2,1,1),
    ('tiny',1,8,8,64,1,0,1),('native_batch',4,32,32,128,1,0,0),
    ('residual',4,64,128,384,1,0,0),
    ('actual_padded_guard',1,1041,1105,1064,1,0,0),
    ('actual_padded_guard',1,1072,1033,1192,2,1,1),
    ('r06_long_k',1,1024,1024,2048,1,0,0),
    ('native_dense',1,256,128,128,1,0,0),
    ('native_narrow',1,4112,48,128,2,1,1),
]:
    specs.append(dict(id=len(specs),label=label,B=B,M=M,N=N,K=K,dtype=dt,ta=ta,tb=tb,pattern='random'))
'''+src[b:]
src=src.replace("default='cases_followup'","default='cases_split_controls'").replace('720928','1030928')
a=src.index('sets={');b=src.index('for name,ids in sets.items():',a)
src=src[:a]+"sets={'manifest':range(len(manifest))}\n"+src[b:]
exec(compile(src,'generate_split_controls_expanded.py','exec'))

from pathlib import Path
import json
root=Path(__file__).resolve().parent;cases=root/'cases';out=root/'san_cases';out.mkdir(exist_ok=True)
meta=[json.loads(x) for x in (cases/'manifest.jsonl').read_text().splitlines()]+json.loads((cases/'boundary_meta.json').read_text())
selected=[]
for dt,ta,tb,M,N,K in [(1,0,0,2,2,32),(2,1,1,3,3,56),(1,1,1,16,16,64),(2,0,0,16,16,64),(1,0,1,16,9,112),(2,1,0,16,9,112)]:
 s=next(x for x in meta if x['B']>=2 and all(x[k]==v for k,v in [('dtype',dt),('ta',ta),('tb',tb),('M',M),('N',N),('K',K)]))
 selected.append(dict(s,B=2,source_B=s['B']))
rows=[]
for s in selected:
 # Each selected source has >=2 batches; logical/physical batch storage is contiguous.
 assert s['source_B']>=2
 B,M,N,K=[s[k] for k in ('B','M','N','K')];cid=s['id']
 for name,nbytes in [('a',B*M*K*2),('b',B*N*K*2),('golden',B*8)]:
  raw=(cases/f'case{cid}_{name}.bin').read_bytes()[:nbytes];assert len(raw)==nbytes
  (out/f'case{cid}_{name}.bin').write_bytes(raw)
 rows.append(' '.join(str(s[k]) for k in ('id','B','M','N','K','dtype','ta','tb')))
(out/'focus.txt').write_text('\n'.join(rows)+'\n');(out/'metadata.json').write_text(json.dumps(selected,indent=2)+'\n')
# A loop/reuse control retains B41; checks are restricted to block 0.
s=next(x for x in meta if x['B']==41 and x['M']==15 and x['N']==9 and x['K']==112 and x['dtype']==1 and x['ta']==0 and x['tb']==0)
(cases/'sanitize_loop.txt').write_text(' '.join(str(s[k]) for k in ('id','B','M','N','K','dtype','ta','tb'))+'\n')
print('FOCUS',len(rows),'B41_LOOP_ID',s['id'])

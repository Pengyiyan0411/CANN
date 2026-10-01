import json
from pathlib import Path
root=Path(__file__).resolve().parent;out=root/'cases'
meta=[json.loads(x) for x in (out/'manifest.jsonl').read_text().splitlines()]
def row(s):return ' '.join(str(s[k]) for k in ('id','B','M','N','K','dtype','ta','tb'))
sel=[]
for s in meta:
 if s['split']=='dot_screen' and s['K'] in (32,40,64,72,128):sel.append(s)
 if s['split']=='micro_screen' and s['B']==32 and (s['M'],s['N'],s['K']) in ((2,2,32),(16,16,64)) and (s['ta'],s['tb']) in ((0,0),(1,1)):sel.append(s)
 if s['split']=='micro_holdout' and s['B']==41 and (s['M'],s['N'],s['K']) in ((15,9,112),(16,7,120)) and (s['ta'],s['tb']) in ((0,1),(1,0)):sel.append(s)
(out/'sanitize.txt').write_text('\n'.join(row(s) for s in sel)+'\n')
print('SANITIZE',len(sel))

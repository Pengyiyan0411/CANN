"""Summarize findings without treating exit 0 or numerical PASS as sanitizer PASS."""
from pathlib import Path
import json,re,collections
r=Path(__file__).resolve().parent;out={}
for v in ['r19','r20','r21']:
    out[v]={}
    for c in ['racecheck','initcheck','memcheck']:
        p=r/'results'/f'c12_{v}_instrumented_{c}.log'
        if not p.exists():continue
        t=p.read_text(errors='replace');lines=(r/f'{v}.asc').read_text().splitlines()
        nums=collections.Counter(re.findall(r'#0 .*'+v+r'.asc:(\d+):',t))
        out[v][c]=dict(errors=t.count('====== ERROR:'),spaces=dict(collections.Counter(re.findall(r' on (GM|UB|L1|L0A|L0B|L0C|PRIVATE) in ',t))),
            findings_by_source=[dict(line=int(n),count=k,source=lines[int(n)-1].strip()) for n,k in nums.most_common()],
            skipped='temporarily ignored' in t,finished_kernel_count=t.count('Sanitizer finished on kernel'),
            messages=collections.Counter(re.sub(r' in ".*','',x) for x in re.findall(r'====== ERROR: ([^\n]+)',t)))
(r/'results/c12_sanitizer_comparison.json').write_text(json.dumps(out,indent=2)+'\n')
for v,checks in out.items():
    for c,d in checks.items():print(v,c,json.dumps({k:d[k] for k in ['errors','spaces','finished_kernel_count','skipped']}))

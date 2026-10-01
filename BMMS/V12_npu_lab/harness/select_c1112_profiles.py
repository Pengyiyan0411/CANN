from pathlib import Path
r=Path(__file__).resolve().parent
for manifest,filename,ids in [('cases_c1112_holdout/manifest.txt','public.txt',[2,6,8,13,18,20,24,31,34,36,41,46,48,54,59,61]),('cases/manifest.txt','c1112_control.txt',[16,19,20,23,24,27,28,31])]:
 p=r/manifest;lines=p.read_text().splitlines();(p.parent/filename).write_text('\n'.join(lines[i] for i in ids)+'\n')

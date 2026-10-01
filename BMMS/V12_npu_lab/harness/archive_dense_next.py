from pathlib import Path
import json,hashlib,zipfile,statistics,re
from summarize_dense_next import events
r=Path(__file__).resolve().parent
def readjson(p):return json.loads(p.read_text())
summary=dict(accepted_baseline='r30',candidate='r33',synthetic_not_hidden=True,
 source_sha256={v:hashlib.sha256((r/f'{v}.asc').read_bytes()).hexdigest() for v in ['r30','r31','r32','r33']},
 binary_sha256={v:hashlib.sha256((r/'build'/v).read_bytes()).hexdigest() for v in ['bench_r30','bench_r33','event_bench_r33','sanitize_r33']},
 screen=readjson(r/'results/dense_next_screen_summary.json'),precision=[],events={},public={},sanitizer={})
for p in sorted((r/'results').glob('r3[123]_*correctness.jsonl')):
 rows=[json.loads(x) for x in p.read_text().splitlines()];assert rows and all(x['pass'] for x in rows),p
 summary['precision'].append(dict(file=p.name,groups=len(rows),calls=sum(x['repeats'] for x in rows),max_tolerance_ratio=max(x['max_tolerance_ratio'] for x in rows)))
for label,man in [('holdout','cases_shortk_final/manifest.txt'),('repeat','cases_shortk_final/manifest.txt'),('aa','cases_shortk/manifest.txt'),('all80','cases_shortk/manifest.txt')]:
 summary['events'][label]=events(r/f'results/r33_{label}_event.jsonl',r/man)
for tag in ['shortk_public','longk_control','c8_control','split_control','other_control']:
 p=r/f'results/r33_{tag}_summary.json';j=readjson(p)
 assert j['source_sha256']['r33']==summary['source_sha256']['r33']
 summary['public'][tag]=j
recheck=r/'results/r33_unchanged_reverse_summary.json'
if recheck.exists():summary['public']['unchanged_reverse']=readjson(recheck)
recheck=r/'results/r33_small_reverse_summary.json'
if recheck.exists():summary['public']['small_reverse']=readjson(recheck)
for kind in ['memcheck','racecheck','initcheck']:
 p=r/f'results/r33_{kind}.log';txt=p.read_text(errors='replace')
 rows=[json.loads(x) for x in (r/f'results/r33_{kind}.jsonl').read_text().splitlines()]
 assert len(rows)==4 and all(x['pass'] for x in rows)
 summary['sanitizer'][kind]=dict(errors=txt.count('====== ERROR:'),warnings=txt.count('====== WARNING:'),register_warnings=txt.count('[mssanitizer] Warning:'),actual_kernel_starts=txt.count('Start '+kind+' sanitizer on kernel'),log_file=p.name,bytes=p.stat().st_size)
summary['sanitizer']['exit_status']=(r/'results/r33_sanitizer_status.txt').read_text()
if (r/'results/r33_pipe_summary.json').exists():summary['pipe']=readjson(r/'results/r33_pipe_summary.json')
(r/'results/dense_next_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
files=set()
for v in ['r31','r32','r33']:
 for p in (r/'results').glob(f'{v}_*'):
  if p.is_file():files.add(p)
 for p in (r/'logs').glob(f'{v}_*'):
  if p.is_file():files.add(p)
 for name in [f'{v}.asc',f'event_bench_{v}.asc']:
  files.add(r/name)
 for root in (r/'profiles').glob(f'{v}_*'):
  for p in root.rglob('*'):
   if p.is_file() and p.suffix in ['.csv','.json']:files.add(p)
for folder in ['cases_shortk','cases_shortk_final']:
 for p in (r/folder).glob('*'):
  if p.suffix in ['.txt','.jsonl']:files.add(p)
for glob in ['dense_next*','shortk*']:
 for p in (r/'results').glob(glob):
  if p.is_file() and p.suffix!='.zip':files.add(p)
for p in (r/'logs').glob('dense_next*'):files.add(p)
for name in ['r30.asc','CMakeLists.txt','main.asc','run_screen.py','run_screen_reverse.py','recheck_r33.sh','generate_shortk.py','generate_shortk_final.py','screen_dense_next.sh','explore_shortk_pitch.sh','validate_r33.sh','summarize_dense_next.py','archive_dense_next.py']:
 files.add(r/name)
hashes={str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
with zipfile.ZipFile(r/'results/dense_next_evidence.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(files):z.write(p,str(p.relative_to(r)))
 z.writestr('SHA256.json',json.dumps(hashes,indent=2)+'\n')
for key,s in summary['events'].items():print(key,len(s['cases']),s['median_reduction_pct'],s['min_reduction_pct'],s['max_reduction_pct'])
print('precision',summary['precision'])
print('sanitizer',summary['sanitizer'])
print('archive files',len(files))

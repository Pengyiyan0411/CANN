from pathlib import Path
import hashlib,json,statistics,zipfile,re
r=Path(__file__).resolve().parents[1];o=r/'BMMS_V12';d=r/'V12_npu_lab/results/dense_pipeline_20260928';e=d/'evidence'
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
with zipfile.ZipFile(d/'dense_pipeline_evidence.zip') as z:
 assert z.testzip() is None
 inv=json.loads(z.read('INVENTORY_SHA256.json'))
 for name,h in inv.items():
  assert not Path(name).is_absolute() and '..' not in Path(name).parts
  assert hashlib.sha256(z.read(name)).hexdigest()==h
 z.extractall(e)
assert sha(e/'r19.asc')==sha(o/'v12_baseline_r19.asc')=='27ff91a8e886644ba99b68e3a59ed4d5ed0a001039d6c56074df098d4c66c021'
screens=json.loads((e/'results/dense_pipeline_event_summary.json').read_text())
metrics=json.loads((e/'results/dense_pipeline_all_metrics.json').read_text())
def event(p):
 rows=[json.loads(s) for s in p.read_text().splitlines()];cs=[]
 for cid in sorted({x['case'] for x in rows}):
  aa,bb=[[x['device_stream_us_per_call'] for x in rows if x['case']==cid and x['label']==l] for l in ['A','B']]
  assert len(aa)==len(bb) and len(aa)>=6
  a,b=statistics.median(aa),statistics.median(bb)
  cs.append(dict(case=cid,base_us=a,candidate_us=b,improvement_pct=100*(1-b/a),paired_improvements_pct=[100*(1-y/x) for x,y in zip(aa,bb)]))
 return dict(file=p.name,cases=cs,median_improvement_pct=statistics.median(x['improvement_pct'] for x in cs),min_improvement_pct=min(x['improvement_pct'] for x in cs),max_improvement_pct=max(x['improvement_pct'] for x in cs))
precision=[]
for v in [28,29,30]:
 m=json.loads((o/f'v12_r{v}_manifest.json').read_text(encoding='utf-8'));assert m['sha256']==sha(e/f'r{v}.asc')==sha(o/m['file'])
 for f in sorted(e.glob(f'results/r{v}_*_correctness.jsonl')):
  rows=[json.loads(s) for s in f.read_text().splitlines()];assert rows and all(x['pass'] for x in rows)
  precision.append(dict(version=f'r{v}',file=f.name,cases=len(rows),calls=sum(x['repeats'] for x in rows),max_tolerance_ratio=max(x['max_tolerance_ratio'] for x in rows)))
assert sum(x['cases'] for x in precision if x['version']=='r30')==372
events={name:event(e/f'results/r30_{name}_event.jsonl') for name in ['holdout','holdout_repeat','balanced','aa']}
public={}
for f in e.glob('results/r30_*_summary.json'):
 q=json.loads(f.read_text())
 if 'source_sha256' in q:
  assert q['source_sha256']['r30']==sha(e/'r30.asc') and q['source_sha256']['r19']==sha(e/'r19.asc')
  public[f.name]=q['summary']
assert len(public)>=5
san={}
for name in ['memcheck','racecheck','initcheck']:
 p=e/f'results/r30_{name}.log';text=p.read_text(errors='replace') if p.exists() else ''
 launcher=(e/f'results/r30_{name}_launcher.log').read_text(errors='replace')
 rows=[json.loads(s) for s in (e/f'results/r30_{name}.jsonl').read_text().splitlines()]
 assert len(rows)==2 and all(x['pass'] for x in rows)
 san[name]=dict(error_reports=len(re.findall(r'====== ERROR:',text)),actual_kernel_starts=text.count('Start '+name+' sanitizer on kernel'),log=p.name,launcher=launcher[-1200:])
for name in ['memcheck','racecheck','initcheck']:
 p=e/f'results/r30_baseline_{name}.log';text=p.read_text(errors='replace')
 rows=[json.loads(s) for s in (e/f'results/r30_baseline_{name}.jsonl').read_text().splitlines()]
 assert len(rows)==2 and all(x['pass'] for x in rows)
 san['baseline_'+name]=dict(error_reports=len(re.findall(r'====== ERROR:',text)),log=p.name)
p=e/'results/r30_synccheck.log';text=p.read_text(errors='replace')
san['synccheck']=dict(error_reports=len(re.findall(r'====== ERROR:',text)),warning_reports=len(re.findall(r'====== WARNING:',text)),log=p.name)
summary=dict(accepted='v12_r19',candidate='v12_r30',candidate_sha256=sha(e/'r30.asc'),synthetic_not_hidden=True,precision=precision,screen=screens,events=events,public=public,sanitizer=san,metrics=metrics,verified_evidence_files=len(inv))
dump(d/'SUMMARY.json',summary)
print('Summary verified; report and promotion decision must be reviewed separately.')
print('SCREEN',[(x['version'],x['median_improvement_pct'],x['min_improvement_pct'],x['max_improvement_pct']) for x in screens])
print('INDEPENDENT',[(k,q['median_improvement_pct'],q['min_improvement_pct'],q['max_improvement_pct']) for k,q in events.items()])
print('SAN', {k:(x['error_reports'],x.get('warning_reports')) for k,x in san.items()})

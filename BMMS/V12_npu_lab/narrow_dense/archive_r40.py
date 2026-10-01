from pathlib import Path
import json,hashlib,zipfile,csv,statistics
root=Path('.').resolve();dest=root/'r40_evidence';dest.mkdir(exist_ok=True)
rows=[]
for f in ['r40_correctness.jsonl','r40_extra_correctness.jsonl']:
 rows += [json.loads(l) for l in (root/'results'/f).read_text().splitlines()]
assert len(rows)==166 and all(r['pass'] for r in rows)
hit={r['case']:r['r40_hit'] for r in rows}
report=json.loads((root/'results/r40_calibration_summary.json').read_text())
cal=[]
for r in report['summary']:
 i=r['case'][0];cal.append(dict(case=r['case'],hit=hit[i],r33_us=r['baseline_median_us'],r40_us=r['candidate_median_us'],ratio=r['candidate_median_us']/r['baseline_median_us']))
# Confirm grid sizes in actual profiler records, not just host log messages.
launch=[]
for run in report['runs']:
 if run['version']!='r40':continue
 fs=list((root/'profiles'/run['run']).glob('PROF_*/mindstudio_profiler_output/op_summary*.csv'))
 assert len(fs)==1
 allrows=[r for r in csv.DictReader(fs[0].open()) if 'bmms' in r.get('Op Name','')]
 allrows.sort(key=lambda r:float(r['Task Start Time(us)']))
 cases=[list(map(int,s.split())) for s in (root/'cases/r40_calibration.txt').read_text().splitlines()]
 idx=[r[0] for r in cases].index(run['case'][0]);rr=allrows[idx*30:(idx+1)*30]
 dims={r['Block Num'] for r in rr};mix={r['Mix Block Num'] for r in rr}
 assert 'missing' not in dims and len(rr)==30
 if hit[run['case'][0]]:assert dims=={'1'},(run,dims)
 launch.append(dict(run=run['run'],case=run['case'][0],hit=hit[run['case'][0]],block_num=sorted(dims),mix_block_num=sorted(mix)))
summary=dict(precision_configurations=166,precision_calls=sum(r['repeats'] for r in rows),all_pass=True,
 hit_configurations=sum(hit.values()),max_tolerance_ratio=max(r['max_tolerance_ratio'] for r in rows),calibration=cal,profiler_launch=launch,
 hit_ratio_range=[min(x['ratio'] for x in cal if x['hit']),max(x['ratio'] for x in cal if x['hit'])],
 miss_ratio_range=[min(x['ratio'] for x in cal if not x['hit']),max(x['ratio'] for x in cal if not x['hit'])])
(root/'results/r40_summary.json').write_text(json.dumps(summary,indent=2))
files=[root/f for f in ['r33.asc','r40.asc','main_r40.asc','CMakeLists.txt','check_r40.sh','archive_r40.py','run_screen.py','generate.py','generate_extra.py','representatives.json']]
for pattern in ['logs/r40*','results/r40*','cases/*.txt','cases/*.jsonl','results/environment.json']:
 files += [p for p in root.glob(pattern) if p.is_file()]
files += list(root.glob('profiles/r40_calibration_*/PROF_*/mindstudio_profiler_output/op_summary*.csv'))
files=sorted(set(files));manifest=dict(files={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},binary_sha256=hashlib.sha256((root/'build/bench_r40').read_bytes()).hexdigest())
(dest/'manifest.json').write_text(json.dumps(manifest,indent=2))
with zipfile.ZipFile(root/'r40_evidence.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in files:z.write(p,p.relative_to(root))
 z.write(dest/'manifest.json','manifest.json')
print(json.dumps(summary,indent=2))

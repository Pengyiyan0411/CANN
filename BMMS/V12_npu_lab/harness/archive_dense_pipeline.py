from pathlib import Path
import csv,json,statistics,zipfile,hashlib
r=Path(__file__).resolve().parent
cases=[list(map(int,s.split())) for s in (r/'cases_c1112_screen/pipe.txt').read_text().splitlines()]
out=[]
for v in ['r19','r26','r28','r29','r30']:
    fs=list((r/f'profiles/dense_pipe_{v}_v1').glob('PROF_*/mindstudio_profiler_output/op_summary*.csv'))
    assert len(fs)==1,(v,fs)
    rows=[x for x in csv.DictReader(fs[0].open()) if 'bmms' in x.get('Op Name','')]
    rows.sort(key=lambda x:float(x['Task Start Time(us)']));assert len(rows)==30*len(cases)
    for i,c in enumerate(cases):
        rr=rows[i*30+10:(i+1)*30];d={'version':v,'case':c,'kernel':rr[0]['Op Name']}
        for k in rr[0]:
            if k in ['Task Duration(us)','aicore_time(us)','Block Num','Mix Block Num','cube_utilization(%)'] or k.startswith(('aic_','aiv_')):
                try:d[k]=statistics.median(float(x[k]) for x in rr)
                except ValueError:pass
        out.append(d)
(r/'results/dense_pipeline_all_metrics.json').write_text(json.dumps(out,indent=2)+'\n')
summaries=[]
for v in [28,29,30]:
    p=r/f'results/r{v}_screen_event.jsonl';rows=[json.loads(x) for x in p.read_text().splitlines()];cc=[]
    for cid in sorted({x['case'] for x in rows}):
        a,b=[[x['device_stream_us_per_call'] for x in rows if x['case']==cid and x['label']==label] for label in ['A','B']]
        assert len(a)==len(b)==6
        aa,bb=statistics.median(a),statistics.median(b)
        cc.append(dict(case=cid,base_us=aa,candidate_us=bb,improvement_pct=(1-bb/aa)*100,paired_improvements_pct=[(1-y/x)*100 for x,y in zip(a,b)]))
    ss=dict(version=f'r{v}',median_improvement_pct=statistics.median(x['improvement_pct'] for x in cc),min_improvement_pct=min(x['improvement_pct'] for x in cc),max_improvement_pct=max(x['improvement_pct'] for x in cc),cases=cc)
    summaries.append(ss);print({k:ss[k] for k in ss if k!='cases'})
(r/'results/dense_pipeline_event_summary.json').write_text(json.dumps(summaries,indent=2)+'\n')
files=set()
for v in [28,29,30]:
    for pat in [f'results/r{v}_*.*',f'logs/r{v}_*.*',f'profiles/r{v}_*/PROF_*/mindstudio_profiler_output/op_summary*.csv']:
        files.update(r.glob(pat))
    for name in [f'r{v}.asc',f'event_bench_r{v}.asc',f'screen_r{v}.sh']:files.add(r/name)
for v in ['r19','r26','r28','r29','r30']:
    files.update((r/f'profiles/dense_pipe_{v}_v1').glob('PROF_*/mindstudio_profiler_output/*.csv'))
    files.update((r/'results').glob(f'dense_pipe_{v}.*'))
for name in ['r19.asc','r26.asc','main.asc','CMakeLists.txt','profile_dense_pipeline.sh','profile_dense_variants.sh','archive_dense_pipeline.py','run_screen.py']:
    files.add(r/name)
for name in ['r30_initial.asc','generate_dense_balanced.py','validate_dense_pipeline.sh','recheck_dense_controls.sh','run_screen_reverse.py','compare_dense_sanitizer.sh']:
    if (r/name).exists():files.add(r/name)
for name in ['dense_pipeline_all_metrics.json','dense_pipeline_event_summary.json']:files.add(r/'results'/name)
for name in ['cases','cases_c1112_screen','cases_c1112_holdout','cases_c8_final','cases_split','cases_split_controls','cases_c12_holdout','cases_r25_values','cases_dense_balanced']:
    files.update((r/name).glob('*.txt'));files.update((r/name).glob('*.jsonl'))
inv={str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files) if p.is_file() and p.suffix!='.zip'}
with zipfile.ZipFile(r/'results/dense_pipeline_evidence.zip','w',zipfile.ZIP_DEFLATED) as z:
    for name in inv:z.write(r/name,name)
    z.writestr('INVENTORY_SHA256.json',json.dumps(inv,indent=2)+'\n')
print('ARCHIVED',len(inv))

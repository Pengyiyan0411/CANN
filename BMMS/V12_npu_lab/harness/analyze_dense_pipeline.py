from pathlib import Path
import csv,json,statistics,zipfile
r=Path(__file__).resolve().parent
cases=[list(map(int,s.split())) for s in (r/'cases_c1112_screen/pipe.txt').read_text().splitlines()]
out=[]
for v in ['r19','r26']:
    files=list((r/f'profiles/dense_pipe_{v}_v1').glob('PROF_*/mindstudio_profiler_output/op_summary*.csv'))
    assert len(files)==1
    rows=[x for x in csv.DictReader(files[0].open()) if 'bmms' in x.get('Op Name','')]
    rows.sort(key=lambda x:float(x['Task Start Time(us)']))
    assert len(rows)==30*len(cases),len(rows)
    print(v,'columns',list(rows[0]))
    for i,c in enumerate(cases):
        rr=rows[i*30+10:(i+1)*30]
        d={'version':v,'case':c,'kernel':rr[0]['Op Name']}
        for k in rr[0]:
            if k=='Task Duration(us)' or k.startswith(('aic_','aiv_')):
                try:d[k]=statistics.median(float(x[k]) for x in rr)
                except ValueError:pass
        out.append(d);print(json.dumps(d))
(r/'results/dense_pipeline_summary.json').write_text(json.dumps(out,indent=2)+'\n')
with zipfile.ZipFile(r/'results/dense_pipeline_profiles.zip','w',zipfile.ZIP_DEFLATED) as z:
    for v in ['r19','r26']:
        for f in (r/f'profiles/dense_pipe_{v}_v1').rglob('*'):
            if f.is_file():z.write(f,str(f.relative_to(r)))
        for f in (r/'results').glob(f'dense_pipe_{v}.*'):z.write(f,str(f.relative_to(r)))
    z.write(r/'results/dense_pipeline_summary.json','results/dense_pipeline_summary.json')

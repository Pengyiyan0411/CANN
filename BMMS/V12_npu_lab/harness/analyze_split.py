import csv, glob, json, statistics
from pathlib import Path
records={x['id']:x for x in map(json.loads,Path('cases_split/manifest.jsonl').read_text().splitlines())}
out={}
for file in sorted(Path('results').glob('split_r*_event_*.jsonl')):
    rows=[json.loads(s) for s in file.read_text().splitlines()];by={}
    for r in rows:by.setdefault(r['case'],{}).setdefault(r['window'],{})[r['label']]=r['device_stream_us_per_call']
    result=[]
    for cid,windows in by.items():
        pairs=[v for v in windows.values() if len(v)==2]
        s=records[cid]
        result.append(dict(case=cid,shape=[s[k] for k in ['B','M','N','K','dtype','ta','tb']],windows=len(pairs),
                           baseline_us=statistics.median(v['A'] for v in pairs),candidate_us=statistics.median(v['B'] for v in pairs),
                           paired_gain_pct=statistics.median(100*(1-v['B']/v['A']) for v in pairs)))
    out[file.stem]=result
    print(file.name,'cases',len(result),'gain min/median/max',*[round(f([x['paired_gain_pct'] for x in result]),3) for f in [min,statistics.median,max]])
    if 'screen' in file.name or 'layouts' in file.name:
        for r in result:print(r)
for version in ['r03','r10','r11','r12']:
    paths=glob.glob(f'profiles/split_pipe_{version}/PROF_*/mindstudio_profiler_output/op_summary*.csv')
    if paths:
        rows=list(csv.DictReader(open(paths[0])))[5:]
        fields=['Task Duration(us)','aic_mac_time(us)','aic_mte1_time(us)','aic_mte2_time(us)','aic_scalar_time(us)','aiv_time(us)','aiv_scalar_time(us)','aiv_vec_time(us)']
        out['pipe_'+version]={k:statistics.median(float(r[k]) for r in rows) for k in fields}
Path('results/split_analysis.json').write_text(json.dumps(out,indent=2)+'\n')

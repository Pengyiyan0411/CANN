from pathlib import Path
import json,hashlib,zipfile,statistics
r=Path(__file__).resolve().parents[1];o=r/'V12_npu_lab/results/b_resident_20260929'
with zipfile.ZipFile(o/'r45_r47_evidence.zip') as z:
    assert z.testzip() is None
    manifest=json.loads(z.read('manifest.json'))
    for name,h in manifest['files'].items():
        assert hashlib.sha256(z.read(name)).hexdigest()==h,name
        p=(o/'evidence'/name).resolve();assert p.is_relative_to((o/'evidence').resolve())
        p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(name))
    (o/'evidence/manifest.json').write_bytes(z.read('manifest.json'))
print('verified files',len(manifest['files']))
allstats={}
for tag in ['r45_screen','r46_screen','r47_screen','r47_holdout']:
    data=json.loads((o/f'evidence/results/{tag}_summary.json').read_text())
    ver=tag.split('_')[0]; ns='bmms12'+ver[1:]
    active={run['case'][0] for run in data['runs'] if run['version']==ver and any(ns in k for k in run['kernels'])}
    selected=[s for s in data['summary'] if s['case'][0] in active]
    red=[100*(1-s['candidate_median_us']/s['baseline_median_us']) for s in selected]
    stats=dict(active_configurations=len(selected),total_configurations=len(data['summary']),wins=sum(x>0 for x in red),median_reduction_percent=statistics.median(red),min_reduction_percent=min(red),max_reduction_percent=max(red),both_windows_faster=sum(all(x>1 for x in s['speedups']) for s in selected))
    allstats[tag]=stats;print(tag,json.dumps(stats))
    for s,d in zip(selected,red):print(s['case'],round(s['baseline_median_us'],3),round(s['candidate_median_us'],3),round(d,3),[round(100*(1-1/x),2) for x in s['speedups']])
(o/'PERFORMANCE.json').write_text(json.dumps(allstats,indent=2)+'\n',encoding='utf-8')

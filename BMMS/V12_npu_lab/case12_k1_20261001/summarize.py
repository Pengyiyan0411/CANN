"""Read existing profiler results without discarding losing shapes."""
from pathlib import Path
import json,statistics,math
root=Path(__file__).resolve().parent
for path in sorted((root/'results').glob('*_summary.json')):
    d=json.loads(path.read_text());rows=d['summary'];candidate=next(v for v in d['source_sha256'] if v!='r41')
    expected='bmms12'+candidate[1:]
    if candidate in ['r51','r52']:
        assert all(all(expected in k for k in r['kernels']) for r in d['runs'] if r['version']==candidate)
        assert all(all('bmms1230_' in k for k in r['kernels']) for r in d['runs'] if r['version']=='r41')
    if candidate=='r53':
        assert all(all('bmms1253_' in k for k in r['kernels']) for r in d['runs'] if r['version']==candidate)
    if candidate=='r54':
        for r in d['runs']:
            kernel='bmms1254_' if r['version']==candidate and r['case'][3]%128==64 else 'bmms1230_'
            assert all(kernel in k for k in r['kernels']),(r['case'],r['kernels'],kernel)
    def metrics(rs):
        gains=[100*(1-r['candidate_median_us']/r['baseline_median_us']) for r in rs]
        return dict(configurations=len(rs),median_latency_reduction_pct=statistics.median(gains),
                    min_pct=min(gains),max_pct=max(gains),positive=sum(x>0 for x in gains),
                    above_one_percent=sum(x>1 for x in gains),below_minus_one_percent=sum(x< -1 for x in gains),
                    both_windows_faster=sum(all(x>1 for x in r['speedups']) for r in rs),
                    geometric_speedup=math.exp(statistics.mean(math.log(r['baseline_median_us']/r['candidate_median_us']) for r in rs)))
    groups={f'dtype{dt}_TA{ta}':metrics([r for r in rows if r['case'][5:7]==[dt,ta]]) for dt in [1,2] for ta in [0,1]}
    result={'source':path.name,'overall':metrics(rows),'groups':groups,
            'N_mod128_64':metrics([r for r in rows if r['case'][3]%128==64]),
            'N_mod128_0':metrics([r for r in rows if r['case'][3]%128==0])}
    print(json.dumps(result,indent=2))
    (root/'results'/path.name.replace('_summary.json','_analysis.json')).write_text(json.dumps(result,indent=2)+'\n')

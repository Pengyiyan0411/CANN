"""Validate manually supplied Judge results; never fabricates device data."""
from pathlib import Path
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import re

HERE=Path(__file__).resolve().parent
T=[1.22,1.58,2.16,2.92,2.38,7.23,3.70,17.32,52.01,72.47,74.82,91.20,9.37,10.11,9.04]
P01=[2.41,5.57,5.23,6.50,7.19,14.41,12.83,90.82,119.83,141.21,171.70,108.87,17.92,14.99,110.22]


def positive(v): return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and v>0


def analyze(data,manifest):
    variants={v['id']:v for v in manifest['variants']}
    if data.get('variant') not in variants:raise ValueError('unknown variant ID')
    variant=variants[data['variant']]
    result=dict(data)
    result['source_sha256']=variant['sha256']
    if data.get('compile_error'):
        result.update(all_15_pass=False,computed_score=None,score_basis='compile_failed')
        return result
    rows=data.get('rows',[])
    if len(rows)!=15 or sorted(r.get('case') for r in rows)!=list(range(1,16)):
        raise ValueError('require exactly cases 1..15')
    rows=sorted(rows,key=lambda r:r['case'])
    for r in rows:
        if r['status'] not in ('Pass','Fail','WA','RE','TLE'):raise ValueError('unrecognized status')
        if r['status']=='Pass' and not positive(r.get('latency_us')):raise ValueError('Pass needs positive finite latency')
    result['rows']=rows
    passed=all(r['status']=='Pass' for r in rows)
    result['all_15_pass']=passed
    result['computed_score']=None
    if not passed:
        result['score_basis']='unscored_due_to_failed_case'
        return result
    fresh=all(positive(r.get('best_us')) for r in rows)
    refs=[r['best_us'] for r in rows] if fresh else T
    result['score_basis']='provided_current_T' if fresh else 'frozen_historical_T_not_current_ranking'
    values=[]
    for r,t,p in zip(rows,refs,P01):
        r['p01_us']=p;r['relative_to_p01_percent']=(r['latency_us']/p-1)*100
        r['T_used']=t
        # An old T is no longer "best" if this submission beats it. Do not
        # pretend the formula with stale T is a valid current score.
        values.append(100/(1+math.log(r['latency_us']/t,1.5)) if r['latency_us']>=t else None)
    if all(v is not None for v in values):result['computed_score']=sum(values)/15
    else:result['score_note']='Some latency beats supplied T; retain raw values, obtain updated T before scoring.'
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);args=p.parse_args()
    manifest=json.loads((HERE/'MANIFEST.json').read_text(encoding='utf-8'))
    data=json.loads(args.input.read_text(encoding='utf-8-sig'))
    result=analyze(data,manifest)
    variant=next(v for v in manifest['variants'] if v['id']==data['variant'])
    actual=hashlib.sha256((HERE/variant['file']).read_bytes()).hexdigest()
    if actual!=variant['sha256']:raise ValueError('local source changed since manifest; restore exact submitted source')
    result['recorded_utc']=datetime.now(timezone.utc).isoformat()
    folder=HERE/'results';folder.mkdir(exist_ok=True)
    label=re.sub(r'[^A-Za-z0-9_-]','_',str(data.get('submission_id','unidentified')))
    output=folder/f'{data["variant"]}_{label}.json'
    with output.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({'record':str(output),'all_15_pass':result['all_15_pass'],
                      'computed_score':result['computed_score'],'score_basis':result['score_basis']},ensure_ascii=False))


if __name__=='__main__':main()

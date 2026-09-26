#!/usr/bin/env python3
"""Summarize real msprof kernel Task Duration. Never use host-call timing.
Usage: python tools/profile_summary.py RESULTS_DIR --contains bmms
A group with multiple task types is not collapsed into an invented kernel time.
"""
from __future__ import annotations
import argparse,csv,json,statistics,math
from pathlib import Path

def quantile(x,p):
    x=sorted(x);t=(len(x)-1)*p;i=int(t);j=min(i+1,len(x)-1)
    return x[i]*(j-t)+x[j]*(t-i) if i!=j else x[i]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('directory',type=Path)
    ap.add_argument('--contains',default='bmms');ap.add_argument('--skip',type=int,default=1,help='One warmup per independent application')
    ap.add_argument('--output',type=Path);a=ap.parse_args();rows=[];warnings=[]
    if a.skip<0:ap.error('skip must be nonnegative')
    for f in sorted(a.directory.rglob('op_summary*.csv')):
        with f.open(encoding='utf-8-sig',newline='') as h:
            reader=csv.DictReader(h);fields=reader.fieldnames or []
            dur=next((k for k in fields if 'Task Duration' in k and ('us' in k or 'μs' in k)),None)
            name=next((k for k in ['Op Name','Name','Kernel Name'] if k in fields),None)
            if not dur or not name:
                warnings.append(f'{f}: missing kernel-name or Task Duration(us) field; not guessed');continue
            grouped={}
            for r in reader:
                if a.contains not in r.get(name,''):continue
                key=(r[name],r.get('Task Type','UNKNOWN'),r.get('Op Type','UNKNOWN'))
                try:v=float(r[dur].replace(',',''))
                except (ValueError,AttributeError):continue
                if v<=0:continue
                metrics={}
                for field,value in r.items():
                    if not field or not any(token in field.lower() for token in ['aic_','aiv_','mte','cube','mac_','vec_','fixpipe']):continue
                    try:metric=float(value.replace(',','').rstrip('%'))
                    except (ValueError,AttributeError):continue
                    if math.isfinite(metric):metrics[field]=metric
                grouped.setdefault(key,[]).append((v,metrics))
            for (kernel,typ,optype),xs in grouped.items():
                records=xs[a.skip:];kept=[x[0] for x in records]
                if not kept:warnings.append(f'{f}: insufficient repetitions for {kernel}');continue
                fields=set().union(*(x[1].keys() for x in records))
                metrics={field:statistics.median([x[1][field] for x in records if field in x[1]]) for field in sorted(fields)}
                rows.append(dict(file=str(f),kernel=kernel,task_type=typ,op_type=optype,count=len(kept),median_us=statistics.median(kept),p10_us=quantile(kept,.1),p90_us=quantile(kept,.9),min_us=min(kept),max_us=max(kept),pipeline_metrics_median=metrics))
            if len(grouped)>1:warnings.append(f'{f}: multiple kernels/task types kept separate; verify one-launch MIX profiling semantics before comparing')
    if not rows:warnings.append('No usable Task Duration measurements found; no performance claim is possible.')
    result=dict(measurement='msprof Task Duration (us), not host elapsed',groups=rows,warnings=warnings)
    text=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if a.output:a.output.write_text(text)
    print(text,end='')
if __name__=='__main__':main()

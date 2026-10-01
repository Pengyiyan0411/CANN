from pathlib import Path
import csv,json,statistics
root=Path(__file__).resolve().parent
fields=['Task Duration(us)','aicore_time(us)','aic_mac_time(us)','aic_mte1_time(us)','aic_mte2_time(us)','aic_fixpipe_time(us)','aic_scalar_time(us)','aiv_time(us)','aiv_vec_time(us)','aiv_mte2_time(us)','aiv_scalar_time(us)']
out={}
for version in ('r41','r63','r64'):
 files=list((root/f'profiles/r64_detail_{version}').glob('PROF_*/mindstudio_profiler_output/op_summary*.csv'))
 assert len(files)==1
 rows=[r for r in csv.DictReader(files[0].open()) if 'bmms' in r['Op Name']]
 rows.sort(key=lambda x:float(x['Task Start Time(us)']));assert len(rows)==10
 for i,cid in enumerate((1064,1125)):
  block=rows[i*5+1:(i+1)*5]
  out.setdefault(str(cid),{})[version]={k:statistics.median(float(r[k]) for r in block) for k in fields}
  out[str(cid)][version]['kernel']=block[0]['Op Name']
(root/'results/r64_counters.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))

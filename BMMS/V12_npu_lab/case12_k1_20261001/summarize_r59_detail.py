from pathlib import Path
import csv,json,statistics
root=Path(__file__).resolve().parent
cols={'PipeUtilization':['Task Duration(us)','aicore_time(us)','aic_mac_time(us)','aic_mte1_time(us)','aic_mte2_time(us)','aic_fixpipe_time(us)','aic_scalar_time(us)','aiv_time(us)','aiv_vec_time(us)','aiv_mte2_time(us)','aiv_mte3_time(us)','aiv_scalar_time(us)'],
      'Memory':['Task Duration(us)','aicore_time(us)','aic_l1_read_bw(GB/s)','aic_l1_write_bw(GB/s)','aic_main_mem_read_bw(GB/s)','aic_main_mem_write_bw(GB/s)']}
out={}
for metric,fields in cols.items():
    out[metric]={}
    for version in ('r41','r59'):
        files=list((root/f'profiles/r59_detail_{version}_{metric}').glob('PROF_*/mindstudio_profiler_output/op_summary*.csv'))
        assert len(files)==1
        rows=[r for r in csv.DictReader(files[0].open()) if 'bmms' in r['Op Name']]
        rows.sort(key=lambda x:float(x['Task Start Time(us)']))
        assert len(rows)==10
        for i,case in enumerate((1000,1005)):
            block=rows[i*5+1:(i+1)*5]
            z={k:statistics.median(float(r[k]) for r in block) for k in fields}
            z['kernel']=block[0]['Op Name']
            out[metric].setdefault(str(case),{})[version]=z
(root/'results/r59_counters.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out['PipeUtilization'],indent=2))

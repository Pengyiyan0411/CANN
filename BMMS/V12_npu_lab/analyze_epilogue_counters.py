from pathlib import Path
import csv,json,statistics
r=Path(__file__).resolve().parents[1];o=r/'V12_npu_lab/results/parallel_epilogue_20260929';root=o/'evidence'
cols={'PipeUtilization':['Task Duration(us)','aicore_time(us)','aic_mac_time(us)','aic_mte1_time(us)','aic_mte2_time(us)','aic_fixpipe_time(us)','aic_scalar_time(us)','aiv_time(us)','aiv_vec_time(us)','aiv_mte2_time(us)','aiv_mte3_time(us)','aiv_scalar_time(us)'], 'Memory':['Task Duration(us)','aicore_time(us)','aic_l1_read_bw(GB/s)','aic_l1_write_bw(GB/s)','aic_main_mem_read_bw(GB/s)','aic_main_mem_write_bw(GB/s)','aiv_ub_read_bw(GB/s)','aiv_ub_write_bw(GB/s)']}
output={}
for metric,fields in cols.items():
    output[metric]={}
    for ver in ['r41','r49']:
        f=list((root/f'profiles/r49_detail_{metric}_{ver}').glob('PROF_*/mindstudio_profiler_output/op_summary*.csv'));assert len(f)==1
        data=sorted([x for x in csv.DictReader(f[0].open()) if 'bmms' in x['Op Name']],key=lambda x:float(x['Task Start Time(us)']))
        assert len(data)==10
        for j,case in enumerate([502,516]):
            rows=data[j*5+1:(j+1)*5]
            z={c:statistics.median(float(x[c]) for x in rows) for c in fields}
            z['kernel']=rows[0]['Op Name'];output[metric].setdefault(str(case),{})[ver]=z
            print(metric,case,ver,z)
(o/'COUNTERS.json').write_text(json.dumps(output,indent=2)+'\n')

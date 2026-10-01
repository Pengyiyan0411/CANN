from pathlib import Path
import subprocess,json
r=Path(__file__).resolve().parents[1];o=r/'V12_npu_lab/results/b_resident_20260929'
prefix=(o/'audit_r47.cpp').read_text(encoding='utf-8').split('int main(){')[0]
code=prefix+r'''
int main(){int M,N,K;while(scanf("%d%d%d",&M,&N,&K)==3){
auto old=bmms1230::MakePlan(1,M,N,K,20),p=bmms1247::MakePlan(1,M,N,K,20);
auto before=bmms11r2::ExistingPeak(old);uint64_t cells=0,input=0,macros=0,allmacros=0;
int total=p.mTiles*p.nTiles;
for(int g=0;g<p.blocks;++g){uint64_t c=0,i=0,ms=0;int first=g*total/p.blocks,last=(g+1)*total/p.blocks;
for(int t=first;t<last;){int row=t/p.nTiles,col=t%p.nTiles,u=std::min(2,std::min(last-t,p.nTiles-col));
int ar=std::min(128,M-row*128),br=std::min(u*128,N-col*128);c+=uint64_t(ar)*br;i+=ar+br;++ms;t+=u;}
cells=std::max(cells,c);input=std::max(input,i);macros=std::max(macros,ms);allmacros+=ms;}
printf("{\"M\":%d,\"N\":%d,\"K\":%d,\"old_pM\":%d,\"old_pN\":%d,\"old_tasks\":%d,\"old_blocks\":%d,\"old_peak_macros\":%llu,\"new_peak_macros\":%llu,\"old_peak_cells\":%llu,\"new_peak_cells\":%llu,\"old_peak_input_rows_cols\":%llu,\"new_peak_input_rows_cols\":%llu,\"old_total_macros\":%d,\"new_total_macros\":%llu}\n",M,N,K,old.pM,old.pN,old.tasks,old.blocks,(unsigned long long)before.tiles,(unsigned long long)macros,(unsigned long long)before.cells,(unsigned long long)cells,(unsigned long long)before.input,(unsigned long long)input,old.mTiles*old.nTiles,(unsigned long long)allmacros);
}}
'''
(o/'plan_cost_r47.cpp').write_text(code,encoding='utf-8')
subprocess.run(['g++','-O2','-std=c++17',str(o/'plan_cost_r47.cpp'),'-o',str(o/'plan_cost_r47.exe')],check=True)
data=json.loads((o/'evidence/results/r47_holdout_summary.json').read_text())
summary=data['summary'][::2]
text=''.join(' '.join(map(str,s['case'][2:5]))+'\n' for s in summary)
out=subprocess.check_output([str(o/'plan_cost_r47.exe')],input=text,text=True)
records=list(map(json.loads,out.splitlines()))
for x,s in zip(records,summary):
    x['case']=s['case'][0];x['fp16_reduction_pct']=100*(1-s['candidate_median_us']/s['baseline_median_us'])
    x['peak_cell_reduction_pct']=100*(1-x['new_peak_cells']/x['old_peak_cells'])
    print(x)
(o/'PLAN_COST.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8')

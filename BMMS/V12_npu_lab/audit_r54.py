"""Verify that r54's only change versus the tested r53 module is its stride gate."""
from pathlib import Path
import json,subprocess
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'V12_npu_lab/results/case12_k1_20261001'
base=(ROOT/'BMMS_V12/v12_baseline_r41.asc').read_bytes().decode()
src=(ROOT/'BMMS_V12/v12_r54_case12_stride_gated_m256.asc').read_bytes().decode()
control=(ROOT/'BMMS_V12/v12_r53_case12_m256_prefetch.asc').read_bytes().decode()
def module(s,v):
    a=s.index(f'// BMMS12{v}_BEGIN');b=s.index(f'// BMMS12{v}_END',a)+len(f'// BMMS12{v}_END\n\n');return s[a:b]
mod=module(src,54);old=module(control,53)
assert mod.replace('1254','1253').replace(' && N%128==64','')==old
hook='    if(bmms1254::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
assert src.replace(mod,'',1).replace(hook,'',1)==base
prefix=(OUT/'host_r53.cpp').read_text().split('namespace bmms1253 {')[0]
for ns,s in [('bmms1253',control),('bmms1254',src)]:
    a=s.index('namespace '+ns+' {');b=s.index('template<class T,bool TA,bool TB>',a);prefix+=s[a:b]+'}\n'
code=prefix+r'''
int main(){int matches=0,active=0,active20=0;
for(int cores=1;cores<=64;++cores)for(int M=1280;M<1536;M+=16)
for(int N=4096;N<6144;N+=64){
 bool old=bmms1253::Eligible(1,M,N,1536,cores),hit=bmms1254::Eligible(1,M,N,1536,cores);
 assert(hit==(old&&N%128==64));++matches;
 if(hit){++active;if(cores==20)++active20;}
}
assert(active20==16);
printf("{\"selector_comparisons\":%d,\"active_plans_all_cores\":%d,\"active_MN_plans_20_cores\":%d}\n",matches,active,active20);
}
'''
(OUT/'host_r54.cpp').write_text(code)
subprocess.run(['g++','-O2','-std=c++17',str(OUT/'host_r54.cpp'),'-o',str(OUT/'host_r54.exe')],check=True)
r=json.loads(subprocess.check_output([str(OUT/'host_r54.exe')],text=True));r.update(parent_recovered_exactly=True,only_difference_from_r53='N%128==64 host selector plus symbol names')
(OUT/'static_r54.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))

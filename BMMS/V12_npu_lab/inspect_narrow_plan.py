from pathlib import Path
import subprocess, json, collections

root=Path(__file__).resolve().parents[1]
src=(root/'BMMS_V12/v12_baseline_r33.asc').read_text()
out=root/'V12_npu_lab/results/narrow_dense_20260929'
out.mkdir(parents=True,exist_ok=True)
start=src.index('namespace bmms11r2 {')
end=src.index('template<class T,bool TA,bool TB>',start)
pre='''#include <cstdint>
#include <cstdio>
namespace bmms83 {
struct NativePlan { int32_t B,M,N,K,mTiles,nTiles,pM,pN,tasks,blocks; };
inline int UpH(int a,int b){return (a+b-1)/b;}
inline int MinH(int a,int b){return a<b?a:b;}
inline int MaxH(int a,int b){return a>b?a:b;}
inline int MinI(int a,int b){return a<b?a:b;}
}
'''
code=pre+src[start:end]+'''}
int main(){
 for(int c: {11,12}) for(int M=c==11?1536:1280;M<(c==11?1792:1536);M+=16)
 for(int N=c==11?2048:4096;N<(c==11?3072:6144);N+=16){
 auto p=bmms11r2::MakePlan(1,M,N,c==11?2048:1536,20);
 auto k=bmms11r2::ExistingPeak(p);
 printf("%d,%d,%d,%d,%d,%d,%d,%llu,%llu,%llu\\n",c,M,N,p.pM,p.pN,p.tasks,p.blocks,k.tiles,k.cells,k.input);
 }
}
'''
code='#include <initializer_list>\n'+code
(out/'planner.cpp').write_text(code)
subprocess.run(['g++','-O2','-std=c++17',str(out/'planner.cpp'),'-o',str(out/'planner.exe')],check=True)
raw=subprocess.check_output([str(out/'planner.exe')],text=True)
(out/'plans.csv').write_text('case,M,N,pM,pN,tasks,blocks,peak_tiles,peak_cells,peak_input\n'+raw)
rows=[list(map(int,l.split(','))) for l in raw.splitlines()]
res={}
for c in [11,12]:
 r=[x for x in rows if x[0]==c]
 cnt=collections.Counter(tuple(x[3:7]) for x in r)
 res[c]={'MN_pairs':len(r),'plans':[dict(pM=k[0],pN=k[1],tasks=k[2],blocks=k[3],count=v) for k,v in sorted(cnt.items())],
 'peak_tiles':sorted(set(x[7] for x in r)),'partial_bytes_range':[min(x[2-1]*x[4]*4 for x in r),max(x[1]*x[4]*4 for x in r)]}
(out/'plan_summary.json').write_text(json.dumps(res,indent=2))
print(json.dumps(res,indent=2))

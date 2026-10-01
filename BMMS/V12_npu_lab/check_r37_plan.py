from pathlib import Path
import subprocess,collections,json
root=Path(__file__).resolve().parents[1];out=root/'V12_npu_lab/results/narrow_dense_20260929'
cpp=(out/'planner.cpp').read_text();cpp=cpp[:cpp.index('int main()')]
cpp+=(root/'V12_npu_lab/narrow_dense/policy.hpp').read_text()
cpp+='''
int main(){
for(int c:{11,12})for(int M=c==11?1536:1280;M<(c==11?1792:1536);M+=16)
for(int N=c==11?2048:4096;N<(c==11?3072:6144);N+=16){
int K=c==11?2048:1536;
auto a=bmms11r2::MakePlan(1,M,N,K,20),b=bmms1237::MakePlan(1,M,N,K,20);
auto x=bmms11r2::ExistingPeak(a),y=bmms11r2::ExistingPeak(b);
printf("%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%llu,%llu\\n",c,M,N,a.pM,a.pN,a.tasks,a.blocks,b.pM,b.pN,b.tasks,b.blocks,x.tiles,y.tiles);
}
}
'''
(out/'compare_plan.cpp').write_text(cpp)
subprocess.run(['g++','-O2','-std=c++17',str(out/'compare_plan.cpp'),'-o',str(out/'compare_plan.exe')],check=True)
raw=subprocess.check_output([str(out/'compare_plan.exe')],text=True);(out/'compare.csv').write_text(raw)
rows=[list(map(int,l.split(','))) for l in raw.splitlines()]
changed=[r for r in rows if r[3:7]!=r[7:11]]
for c in [11,12]:
 rr=[r for r in changed if r[0]==c]
 print(c,'changed',len(rr),'transitions',collections.Counter((tuple(r[3:7]),tuple(r[7:11]),r[11],r[12]) for r in rr))
reps={}
for r in changed:
 if r[1]%64 or r[2]%64:continue
 key=(r[0],tuple(r[3:7]),tuple(r[7:11]),r[11],r[12])
 reps.setdefault(key,r)
(out/'representatives.json').write_text(json.dumps(list(reps.values()),indent=2))
print('aligned representatives',list(reps.values()))

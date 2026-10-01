from pathlib import Path
import subprocess,json
root=Path(__file__).resolve().parents[1];out=root/'V12_npu_lab/results/narrow_dense_20260929'
code=(out/'compare_plan.cpp').read_text().split('int main()')[0]
code='#include <cassert>\n'+code+'''
int main(){
long long count=0,changed=0;
for(int cores:{1,2,4,8,16,20,24,32,64})
for(int c:{11,12})for(int M=c==11?1536:1280;M<(c==11?1792:1536);M+=16)
for(int N=c==11?2048:4096;N<(c==11?3072:6144);N+=16){
const int K=c==11?2048:1536;
auto old=bmms11r2::MakePlan(1,M,N,K,cores),p=bmms1237::MakePlan(1,M,N,K,cores);
assert(p.B==1&&p.M==M&&p.N==N&&p.K==K);
assert(p.pM>=1&&p.pM<=p.mTiles&&p.pN>=1&&p.pN<=p.nTiles);
assert(p.tasks==p.pM*p.pN&&p.blocks>=1&&p.blocks<=cores&&p.blocks<=p.tasks);
long long cells=0,macros=0;
for(int t=0;t<p.tasks;++t){int ms=t/p.pN,ns=t%p.pN;
int m0=ms*p.mTiles/p.pM,m1=(ms+1)*p.mTiles/p.pM;
int n0=ns*p.nTiles/p.pN,n1=(ns+1)*p.nTiles/p.pN;
assert(m0<m1&&n0<n1);
int mr=bmms83::MinH(m1*128,M)-m0*128,nr=bmms83::MinH(n1*256,N)-n0*256;
cells+=(long long)mr*nr;macros+=(m1-m0)*(n1-n0);
}
assert(cells==(long long)M*N&&macros==(long long)p.mTiles*p.nTiles);
if(p.pM!=old.pM||p.pN!=old.pN){
 ++changed;assert(p.blocks==p.tasks);auto a=bmms11r2::ExistingPeak(old),b=bmms11r2::ExistingPeak(p),q=bmms11r2::SingleWavePeak(p);
 assert(b.tiles<a.tiles&&b.cells<=a.cells&&b.input<=a.input);
 assert(q.tiles==b.tiles&&q.cells==b.cells&&q.input==b.input);
}
auto shortk=bmms1237::MakePlan(1,M,N,1280,cores),ref=bmms11r2::MakePlan(1,M,N,1280,cores);
assert(shortk.pM==ref.pM&&shortk.pN==ref.pN&&shortk.tasks==ref.tasks&&shortk.blocks==ref.blocks);
++count;
}
printf("{\\"configurations\\":%lld,\\"changed\\":%lld,\\"all_pass\\":true}\\n",count,changed);
}
'''
(out/'audit.cpp').write_text(code)
subprocess.run(['g++','-O2','-std=c++17',str(out/'audit.cpp'),'-o',str(out/'audit.exe')],check=True)
r=subprocess.check_output([str(out/'audit.exe')],text=True)
(out/'audit.json').write_text(r);print(r)

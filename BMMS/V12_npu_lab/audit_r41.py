from pathlib import Path
import subprocess,json
root=Path(__file__).resolve().parents[1];out=root/'V12_npu_lab/results/plan_equal_20260929'
code=(root/'V12_npu_lab/results/narrow_dense_20260929/audit.cpp').read_text(encoding='utf-8').split('// BMMS1237_PLAN_BEGIN')[0]
src=(root/'BMMS_V12/v12_r41_dense_flat_macro.asc').read_text(encoding='utf-8')
for ns in ['bmms1230','bmms1241']:
 a=src.index('namespace '+ns+' {');b=src.index('template<class T,bool TA,bool TB>',a);code+=src[a:b]+'}\n'
code+='''
int main(){
long long count=0,active=0;unsigned long long maxUB=0,maxWS=0;
for(int cores:{1,2,4,8,16,20,24,32,64})for(int c:{11,12})
for(int M=c==11?1536:1280;M<(c==11?1792:1536);M+=16)
for(int N=c==11?2048:4096;N<(c==11?3072:6144);N+=16){
 int K=c==11?2048:1536;++count;
 assert(!bmms1241::Eligible(1,M,N,1280,cores));
 if(!bmms1241::Eligible(1,M,N,K,cores))continue;
 ++active;auto p=bmms1241::MakePlan(1,M,N,K,cores);auto old=bmms11r2::MakePlan(1,M,N,K,cores);
 int total=p.mTiles*p.nTiles,seen=0,prev=0;long long cells=0;
 assert(p.pN==p.blocks&&p.pM==1&&p.tasks==p.blocks&&p.blocks<=cores&&p.blocks<=total);
 for(int g=0;g<p.blocks;++g){
  int first=g*total/p.blocks,last=(g+1)*total/p.blocks;assert(first==prev&&last>first);prev=last;
  assert(last-first<=bmms83::UpH(total,p.blocks));
  for(int t=first;t<last;++t){int m=t/p.nTiles*128,n=t%p.nTiles*256,ar=bmms83::MinH(128,M-m),br=bmms83::MinH(256,N-n);
   assert(ar>0&&ar%16==0&&br>0&&br%16==0);cells+=(long long)ar*br;++seen;
   for(int sub=0;sub<2;++sub){int vr=ar/2;assert(m/2+vr<=M/2);assert(m+sub*vr+vr<=M);}
  }
  // Both subworkers write disjoint adjacent halves of every row tile.
  int written=0;
  for(int m=0;m<M;m+=128){int vr=bmms83::MinH(128,M-m)/2;for(int sub=0;sub<2;++sub){
   long long dst=(long long)g*M+m+sub*vr;assert(dst>=(long long)g*M&&dst+vr<=(long long)(g+1)*M);written+=vr;
  }}assert(written==M);
 }
 assert(prev==total&&seen==total&&cells==(long long)M*N);
 assert((unsigned)bmms83::UpH(total,p.blocks)<bmms11r2::ExistingPeak(old).tiles);
 unsigned long long ub=65536+32+256+((M/2*4+31)/32)*32+3*M*4;
 if(ub>maxUB)maxUB=ub;if(bmms11r2::WorkspaceBytes(p)>maxWS)maxWS=bmms11r2::WorkspaceBytes(p);
 assert(ub<192*1024);assert(bmms11r2::PartialBytes(p)==(unsigned long long)p.blocks*M*4);
}
printf("{\\"configurations\\":%lld,\\"active\\":%lld,\\"max_ub_bytes\\":%llu,\\"max_workspace_bytes\\":%llu,\\"all_pass\\":true}\\n",count,active,maxUB,maxWS);
}
'''
(out/'audit_r41.cpp').write_text(code,encoding='utf-8')
subprocess.run(['g++','-O2','-std=c++17',str(out/'audit_r41.cpp'),'-o',str(out/'audit_r41.exe')],check=True)
result=subprocess.check_output([str(out/'audit_r41.exe')],text=True);json.loads(result);(out/'audit_r41.json').write_text(result,encoding='utf-8');print(result)

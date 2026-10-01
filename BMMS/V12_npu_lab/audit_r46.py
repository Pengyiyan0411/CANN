from pathlib import Path
import subprocess,json
r=Path(__file__).resolve().parents[1];o=r/'V12_npu_lab/results/b_resident_20260929';o.mkdir(exist_ok=True)
prefix=(r/'V12_npu_lab/results/plan_equal_20260929/audit_r41.cpp').read_text(encoding='utf-8').split('int main(){')[0]
s=(r/'BMMS_V12/v12_r46_case12_fractional_n.asc').read_text(encoding='utf-8');a=s.index('namespace bmms1246 {');b=s.index('template<class T,bool TA,bool TB>',a)
code='#include <algorithm>\n#include <vector>\n'+prefix+s[a:b]+'}\n'+'''
int main(){
 long long configs=0,active=0,macros=0,halves=0,mergeReads=0;size_t maxub=0;
 for(int cores:{2,4,8,16,20,24,32,64})for(int M=1280;M<1536;M+=16)for(int N=4096;N<6144;N+=16){
  ++configs;if(!bmms1246::Eligible(1,M,N,1536,cores))continue;++active;
  auto p=bmms1246::MakePlan(1,M,N,1536,cores);int total=p.mTiles*p.nTiles;
  std::vector<int> seen(total,0);long long area=0;
  for(int g=0;g<p.blocks;++g){
   int first=g*total/p.blocks,last=(g+1)*total/p.blocks;
   for(int t=first;t<last;){
    int row=t/p.nTiles,col=t%p.nTiles,u=std::min(2,std::min(last-t,p.nTiles-col));
    int ar=std::min(128,M-row*128),br=std::min(u*128,N-col*128);
    assert(ar>0&&br>0&&ar%16==0&&br%16==0);area+=(long long)ar*br;++macros;
    for(int j=0;j<u;++j)++seen[t+j];t+=u;
   }
  }
  assert(area==(long long)M*N);for(int c:seen)assert(c==1);
  int rows=0;std::vector<int> jobs(2*p.mTiles,0);
  for(int worker=0;worker<2*p.blocks;++worker){
   assert((long long)worker*8+1<=(long long)2*p.blocks*8);
   for(int job=worker;job<2*p.mTiles;job+=2*p.blocks){
    ++jobs[job];++halves;int row=job/2,sub=job%2,ar=std::min(128,M-row*128),vr=ar/2;
    int mStart=row*128+sub*vr;assert(mStart>=0&&mStart+vr<=M);rows+=vr;
    int rf=row*p.nTiles,rl=(row+1)*p.nTiles;
    int gf=((rf+1)*p.blocks-1)/total,gl=(rl*p.blocks-1)/total;
    assert(0<=gf&&gf<=gl&&gl<p.blocks);
    for(int g=0;g<p.blocks;++g){int first=g*total/p.blocks,last=(g+1)*total/p.blocks;
     assert((g>=gf&&g<=gl)==(first<rl&&last>rf));
     if(g>=gf&&g<=gl){++mergeReads;assert((long long)g*M+mStart+vr<=(long long)p.blocks*M);}
    }
   }
  }
  assert(rows==M);for(int c:jobs)assert(c==1);
  assert(2*p.blocks<=255);
  size_t ub=65536+32+256+((M/2*4+31)/32)*32+2*256+2*(2*p.blocks*8*4)+32;
  maxub=std::max(maxub,ub);assert(ub<192*1024);
  assert(bmms1246::WorkspaceBytes(p)==size_t(p.blocks)*2*32768*4+size_t(p.blocks)*M*4+size_t(2*p.blocks)*8*4);
 }
 for(int M=1536;M<1792;M+=16)assert(!bmms1246::Eligible(1,M,2048,2048,20));
 printf("{\\"configurations\\":%lld,\\"active\\":%lld,\\"macros\\":%lld,\\"row_halves\\":%lld,\\"sparse_merge_reads\\":%lld,\\"max_ub_bytes\\":%zu,\\"all_pass\\":true}\\n",configs,active,macros,halves,mergeReads,maxub);
}
'''
(o/'audit_r46.cpp').write_text(code,encoding='utf-8');subprocess.run(['g++','-O2','-std=c++17',str(o/'audit_r46.cpp'),'-o',str(o/'audit_r46.exe')],check=True)
z=subprocess.check_output([str(o/'audit_r46.exe')],text=True);json.loads(z);(o/'audit_r46.json').write_text(z,encoding='utf-8');print(z)

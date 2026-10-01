from pathlib import Path
import json,subprocess
r=Path(__file__).resolve().parents[1];o=r/'V12_npu_lab/results/b_resident_20260929';o.mkdir(exist_ok=True)
prefix=(r/'V12_npu_lab/results/plan_equal_20260929/audit_r41.cpp').read_text(encoding='utf-8').split('int main(){')[0]
src=(r/'BMMS_V12/v12_r45_case12_b_resident.asc').read_text(encoding='utf-8');a=src.index('namespace bmms1245 {');b=src.index('template<class T,bool TA,bool TB>',a)
code='#include <algorithm>\n#include <vector>\n'+prefix+src[a:b]+'}\n'+'''
int main(){
long long configs=0,active=0,macros=0;size_t maxub=0;
for(int cores:{2,4,8,16,20,24,32,64})for(int M=1280;M<1536;M+=16)for(int N=4096;N<6144;N+=16){
 ++configs;assert(!bmms1245::Eligible(1,M,N,1280,cores));
 if(!bmms1245::Eligible(1,M,N,1536,cores))continue;
 ++active;auto p=bmms1245::MakePlan(1,M,N,1536,cores);
 assert(!bmms1241::Eligible(1,M,N,1536,cores));
 assert(bmms11r2::ExistingPeak(p).tiles==(unsigned)bmms83::UpH(p.mTiles*p.nTiles,cores));
 long long area=0;std::vector<int> rowcount(p.pN,0);
 for(int g=0;g<p.blocks;++g)for(int task=g;task<p.tasks;task+=p.blocks){
  int ms=task/p.pN,ns=task%p.pN;
  int m0=ms*p.mTiles/p.pM*128,m1=std::min((ms+1)*p.mTiles/p.pM*128,M);
  int n0=ns*p.nTiles/p.pN*256,n1=std::min((ns+1)*p.nTiles/p.pN*256,N);
  assert(m0<m1&&n0<n1);rowcount[ns]+=m1-m0;
  for(int n=n0;n<n1;n+=128)for(int m=m0;m<m1;m+=128){
   int ar=std::min(128,m1-m),br=std::min(128,n1-n);area+=(long long)ar*br;++macros;
   assert(ar%16==0&&br%16==0);for(int sub=0;sub<2;++sub){int vr=ar/2;
    assert(m/2+vr<=M/2);long long addr=(long long)ns*M+m+sub*vr;
    assert(addr>=(long long)ns*M&&addr+vr<=(long long)(ns+1)*M);
   }
  }
 }
 assert(area==(long long)M*N);for(int c:rowcount)assert(c==M);
 size_t ub=32768+32+256+((M/2*4+31)/32)*32+3*M*4;maxub=std::max(maxub,ub);assert(ub<192*1024);
 assert(bmms1245::WorkspaceBytes(p)==size_t(p.blocks)*2*128*128*4+size_t(p.pN)*M*4);
}
for(int M=1536;M<1792;M+=16)assert(!bmms1245::Eligible(1,M,2048,2048,20));
// Validate full-K resident-B NZ microblock coverage in both physical layouts.
long long bblocks=0;
for(int K=1536;K<1664;K+=32)for(int br=16;br<=128;br+=16)for(int tb=0;tb<2;++tb){
 assert(2*128*192*2+128*K*2<=512*1024);std::vector<int> seen(K*br/256,0);
 for(int k=0;k<K;k+=192){int kr1=std::min(192,K-k);
  for(int kk=0;kk<kr1;kk+=64){int kr0=std::min(64,kr1-kk),bk=k+kk;
   for(int j=0;j<kr0/16;++j)for(int i=0;i<br/16;++i){
    int offset=tb?(bk/16+j)*br*16:(bk+j*16)*16;
    int address=offset+i*(tb?1:K/16)*256;
    assert(address>=0&&address+256<=K*br&&address%256==0);++seen[address/256];++bblocks;
   }
   for(int ar=16;ar<=128;ar+=16)for(int ta=0;ta<2;++ta)for(int i=0;i<ar/16;++i)for(int j=0;j<kr0/16;++j){
    int offset=ta?i*kr1*16+kk*16:(kk/16)*ar*16+i*256;
    int address=offset+j*(ta?1:ar/16)*256;assert(address>=0&&address+256<=ar*kr1);
   }
  }
 }
 for(int x:seen)assert(x==1);
}
printf("{\\"configurations\\":%lld,\\"active\\":%lld,\\"submacros\\":%lld,\\"resident_B_microblocks\\":%lld,\\"max_ub_bytes\\":%zu,\\"all_pass\\":true}\\n",configs,active,macros,bblocks,maxub);
}
'''
(o/'audit_r45.cpp').write_text(code,encoding='utf-8');subprocess.run(['g++','-O2','-std=c++17',str(o/'audit_r45.cpp'),'-o',str(o/'audit_r45.exe')],check=True)
result=subprocess.check_output([str(o/'audit_r45.exe')],text=True);json.loads(result);(o/'audit_r45.json').write_text(result,encoding='utf-8');print(result)

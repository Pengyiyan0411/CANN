from pathlib import Path
import json,subprocess
root=Path(__file__).resolve().parents[1];out=root/'V12_npu_lab/results/wide_pingpong_20260929';out.mkdir(exist_ok=True)
code='#include <algorithm>\n'+(root/'V12_npu_lab/results/plan_equal_20260929/audit_r41.cpp').read_text(encoding='utf-8').split('int main(){')[0]
src=(root/'BMMS_V12/v12_r42_wide_halfm_pingpong.asc').read_text(encoding='utf-8')
a=src.index('namespace bmms1242 {');b=src.index('template<class T,bool TA,bool TB>',a);code+=src[a:b]+'}\n'
code+='''
int main(){
long long configs=0,macros=0,cells=0;size_t maxub=0;
for(int cores:{2,4,8,16,20,24,32,64})for(int M=1280;M<1536;M+=16)for(int N=4096;N<6144;N+=16){
 assert(bmms1242::Eligible(1,M,N,1536,cores));
 assert(!bmms1242::Eligible(1,M,N,1280,cores));
 auto p=bmms1242::MakePlan(1,M,N,1536,cores);++configs;
 int total=p.mTiles*p.nTiles,prev=0,seen=0;long long area=0;
 assert(p.blocks<=cores&&p.pN==p.blocks&&p.pM==1&&p.tasks==p.blocks);
 for(int g=0;g<p.blocks;++g){
  int first=g*total/p.blocks,last=(g+1)*total/p.blocks;
  assert(first==prev&&last>first);prev=last;
  assert(last-first<=bmms83::UpH(total,p.blocks));
  for(int t=first;t<last;++t){
   int m=t/p.nTiles*64,n=t%p.nTiles*256,ar=std::min(64,M-m),br=std::min(256,N-n);
   assert(ar>0&&ar%16==0&&br>0&&br%16==0);++seen;area+=(long long)ar*br;
   for(int sub=0;sub<2;++sub){int vr=ar/2;assert(m/2+vr<=M/2);assert(m+sub*vr+vr<=M);}
  }
  int rows=0;
  for(int m=0;m<M;m+=64){int vr=std::min(64,M-m)/2;
   for(int sub=0;sub<2;++sub){long long addr=(long long)g*M+m+sub*vr;assert(addr>=(long long)g*M&&addr+vr<=(long long)(g+1)*M);rows+=vr;}
  }assert(rows==M);
 }
 assert(prev==total&&seen==total&&area==(long long)M*N);macros+=seen;cells+=area;
 size_t ub=32768+32+128+((M/2*4+31)/32)*32+3*M*4;maxub=std::max(maxub,ub);assert(ub<192*1024);
 assert(bmms1242::RingBytes(p)==size_t(p.blocks)*2*64*256*4);
 assert(bmms1242::WorkspaceBytes(p)==size_t(p.blocks)*(2*64*256+M)*4);
}
for(int M=1536;M<1792;M+=16)assert(!bmms1242::Eligible(1,M,2048,2048,20));
// Explicit operand capacity checks for every live aligned edge extent and K stage tail.
for(int ar=16;ar<=64;ar+=16)for(int br=16;br<=256;br+=16)for(int K=1536;K<1664;K+=32)
for(int k=0;k<K;k+=384){int kr1=std::min(384,K-k);assert(kr1%32==0);
 for(int kk=0;kk<kr1;kk+=64){int kr0=std::min(64,kr1-kk);
  assert(ar*kr0<=64*64&&br*kr0<=256*64&&ar*br<=64*256);
  for(int ta=0;ta<2;++ta)for(int i=0;i<ar/16;++i)for(int j=0;j<kr0/16;++j){
   int off=ta?i*kr1*16+kk*16:(kk/16)*ar*16+i*256;
   int address=off+j*(ta?1:ar/16)*256;assert(address>=0&&address+256<=ar*kr1);
  }
  for(int tb=0;tb<2;++tb)for(int j=0;j<kr0/16;++j)for(int i=0;i<br/16;++i){
   int off=tb?(kk/16+j)*br*16:(kk+j*16)*16;
   int address=off+i*(tb?1:kr1/16)*256;assert(address>=0&&address+256<=br*kr1);
  }
 }
}
// FIX_M ownership: each accumulator is reclaimed exactly before its third use.
for(int length=1;length<=64;++length){bool outstanding[2]={false,false};
 for(int seq=0;seq<length;++seq){int slot=seq%2;if(seq>=2){assert(outstanding[slot]);outstanding[slot]=false;}assert(!outstanding[slot]);outstanding[slot]=true;}
 for(int slot=0;slot<std::min(2,length);++slot){assert(outstanding[slot]);outstanding[slot]=false;}
 assert(!outstanding[0]&&!outstanding[1]);
}
printf("{\\"configurations\\":%lld,\\"macros\\":%lld,\\"cells\\":%lld,\\"max_ub_bytes\\":%zu,\\"all_pass\\":true}\\n",configs,macros,cells,maxub);
}
'''
(out/'audit_r42.cpp').write_text(code,encoding='utf-8')
subprocess.run(['g++','-O2','-std=c++17',str(out/'audit_r42.cpp'),'-o',str(out/'audit_r42.exe')],check=True)
r=subprocess.check_output([str(out/'audit_r42.exe')],text=True);json.loads(r);(out/'audit_r42.json').write_text(r,encoding='utf-8');print(r)

from pathlib import Path
import subprocess,json
r=Path(__file__).resolve().parents[1];d=r/'V12_npu_lab/host_c12';d.mkdir(exist_ok=True)
s=(r/'BMMS_V12/v12_r20_case12_packet_plan.asc').read_text(encoding='utf-8')
pre='''#include <algorithm>
#include <array>
#include <vector>
#include <iostream>
#include <random>
#include <stdexcept>
#include <cstdint>
namespace bmms83{
static int MinH(int a,int b){return std::min(a,b);}static int MaxH(int a,int b){return std::max(a,b);}
static int MinI(int a,int b){return std::min(a,b);}static int UpH(int a,int b){return(a+b-1)/b;}
struct NativePlan{int B,M,N,K,mTiles,nTiles,pM,pN,tasks,blocks;};}
'''
a=s.index('namespace bmms11r2 {');b=s.index('static inline uint64_t RingBytes',a)
pre+=s[a:b]+'}\n'
a=s.index('namespace bmms1220 {');b=s.index('static inline bool TryLaunch',a)
pre+=s[a:b]+'}\n'
test=r'''
using Plan=bmms11r2::Plan;
void need(bool x,const char* why){if(!x)throw std::runtime_error(why);}
// Independent macro-centric ownership. No task-rectangle traversal from the
// production cost formula is reused here.
bmms11r2::GridPeak walk(const Plan& p){
 std::vector<std::array<uint64_t,3>> w(p.blocks);
 std::vector<int> seen(p.mTiles*p.nTiles);
 for(int m=0;m<p.mTiles;++m)for(int n=0;n<p.nTiles;++n){
  const int ms=((m+1)*p.pM-1)/p.mTiles,ns=((n+1)*p.pN-1)/p.nTiles;
  const int task=ms*p.pN+ns,core=task%p.blocks;
  const int mr=std::min(128,p.M-m*128),nr=std::min(256,p.N-n*256);
  need(ms>=0&&ms<p.pM&&ns>=0&&ns<p.pN&&mr>0&&nr>0,"bad ownership");
  ++seen[m*p.nTiles+n];++w[core][0];w[core][1]+=uint64_t(mr)*nr;w[core][2]+=mr+nr;
 }
 for(auto n:seen)need(n==1,"duplicate macro");
 // Every partial(ns,row) belongs to exactly one M shard; producer/consumer
 // both use the same task-to-core rule. Last live row must be included.
 for(int ns=0;ns<p.pN;++ns){int cursor=0;
  for(int ms=0;ms<p.pM;++ms){int lo=ms*p.mTiles/p.pM*128,hi=std::min(p.M,(ms+1)*p.mTiles/p.pM*128);
   need(lo==cursor&&hi>lo,"partial gap/overlap");cursor=hi;}
  need(cursor==p.M,"partial tail missing");
 }
 bmms11r2::GridPeak z{};
 for(auto x:w){z.tiles=std::max(z.tiles,x[0]);z.cells=std::max(z.cells,x[1]);z.input=std::max(z.input,x[2]);}return z;
}
int main(){try{
 std::mt19937 gen(2020928);int changed=0,count=0,guards=0;
 for(int i=0;i<3000;++i){int M=1024+16*(gen()%449),N=1024+16*(gen()%449),K=1536+32*(gen()%16),c=1+gen()%64;
  auto a=bmms11r2::MakePlan(1,M,N,K,c),b=bmms1220::MakePlan(1,M,N,K,c);
  auto wa=walk(a),wb=walk(b),pa=bmms11r2::ExistingPeak(a),pb=bmms11r2::ExistingPeak(b);
  need(wa.tiles==pa.tiles&&wa.cells==pa.cells&&wa.input==pa.input,"baseline peak mismatch");
  need(wb.tiles==pb.tiles&&wb.cells==pb.cells&&wb.input==pb.input,"candidate peak mismatch");
  need(b.tasks==b.pM*b.pN&&b.blocks==std::min(c,b.tasks),"bad launch");
  if(bmms1220::Changed(a,b)){++changed;need(10*wb.tiles<=9*wa.tiles&&wb.cells<=wa.cells&&wb.input<=wa.input,"margin invalid");need(b.pM==b.mTiles&&b.pN==b.nTiles,"not a single macro packet");}
  ++count;
 }
 for(int B:{1,2})for(int K:{128,1024,1504,1536,2016,2048,4096})for(int M:{512,1024,1040,8192})for(int N:{512,1024,2064,8192}){
  if(!bmms1220::Eligible(B,M,N,K,20)){
   auto a=bmms11r2::MakePlan(B,M,N,K,20),b=bmms1220::MakePlan(B,M,N,K,20);
   need(!bmms1220::Changed(a,b),"out of scope changed");++guards;
  }
 }
 std::cout<<"{\"shape_core_checks\":"<<count<<",\"changed\":"<<changed<<",\"out_of_scope_checks\":"<<guards<<",\"passed\":true}\n";
}catch(const std::exception&e){std::cerr<<e.what();return 1;}}
'''
(d/'host.cpp').write_text(pre+test,encoding='utf-8')
subprocess.run(['C:/msys64/ucrt64/bin/g++.exe','-std=c++17','-O2',str(d/'host.cpp'),'-o',str(d/'host.exe')],check=True)
p=subprocess.run([str(d/'host.exe')],capture_output=True,text=True,check=True)
(d/'RESULTS.json').write_text(p.stdout,encoding='utf-8');print(p.stdout)

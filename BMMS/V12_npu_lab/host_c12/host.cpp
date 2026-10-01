#include <algorithm>
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
namespace bmms11r2 {
constexpr int32_t TM=64,TN=128,AM=128,BN=256,K1=256,K0=64;
constexpr int32_t MACRO_ELEMS=4*TM*TN;
constexpr uint16_t READY=4,FREE=6;
using Plan=bmms83::NativePlan;
using bmms83::MinI;
static inline bool Eligible(int32_t B,int32_t M,int32_t N,int32_t K,int32_t cores){
    return B>=1&&B<=64&&cores>=1&&cores<=64&&M>=AM&&M<=8192&&N>=BN&&N<=8192&&
        K>=K1&&K<=8192&&M%16==0&&N%16==0&&K%32==0&&
        int64_t(B)*M*K<=(1LL<<26)&&int64_t(B)*N*K<=(1LL<<26)&&
        int64_t(B)*bmms83::UpH(M,AM)*bmms83::UpH(N,BN)>=cores;
}
// Closed-form peak work for one task per AIC group. No per-task grid search.
struct GridPeak { uint64_t tiles=0,cells=0,input=0; };
static inline int PeakExtent(int extent,int tile,int shards){
    const int tiles=bmms83::UpH(extent,tile),q=tiles/shards,r=tiles%shards;
    if(shards==1)return extent;
    // If the remainder is one, the only long shard is the final (possibly ragged) one.
    if(r==1)return extent-(shards-1)*q*tile;
    return (q+(r!=0))*tile;
}
static inline GridPeak SingleWavePeak(const Plan& p){
    const uint64_t mt=bmms83::UpH(p.mTiles,p.pM),nt=bmms83::UpH(p.nTiles,p.pN);
    const uint64_t mr=PeakExtent(p.M,AM,p.pM),nr=PeakExtent(p.N,BN,p.pN);
    return GridPeak{mt*nt,mr*nr,mr*nt+nr*mt};
}
static inline Plan MakeR10Plan(int32_t B,int32_t M,int32_t N,int32_t K,int32_t cores){
    Plan p{};p.B=B;p.M=M;p.N=N;p.K=K;
    p.mTiles=bmms83::UpH(M,AM);p.nTiles=bmms83::UpH(N,BN);
    cores=bmms83::MaxH(1,cores);
    p.pM=bmms83::MinH(p.mTiles,bmms83::MaxH(1,bmms83::UpH(cores,B)));
    p.pN=bmms83::MinH(p.nTiles,bmms83::MaxH(1,bmms83::UpH(cores,B*p.pM)));
    p.tasks=B*p.pM*p.pN;p.blocks=bmms83::MinH(cores,p.tasks);
    // Keep every original multi-task/partially occupied launch byte-for-byte in Plan.
    if(cores>64||p.tasks!=cores)return p;
    const GridPeak baseline=SingleWavePeak(p);
    Plan best=p;uint64_t bestTiles=baseline.tiles,bestCells=baseline.cells,bestInput=baseline.input;
    const int grid=cores/B;
    for(int pm=1;pm<=bmms83::MinH(p.mTiles,grid);++pm){
        if(grid%pm)continue;
        const int pn=grid/pm;if(pn>p.nTiles)continue;
        Plan candidate=p;candidate.pM=pm;candidate.pN=pn;
        const GridPeak peak=SingleWavePeak(candidate);
        if(8*peak.tiles>7*baseline.tiles||8*peak.cells>7*baseline.cells||
           8*peak.input>7*baseline.input)continue;
        // Deterministic integer ranking. No floating-point cost model or host memoization.
        if(peak.tiles<bestTiles||(peak.tiles==bestTiles&&
           (peak.cells<bestCells||(peak.cells==bestCells&&
           (peak.input<bestInput||(peak.input==bestInput&&pn<best.pN)))))){
            best=candidate;bestTiles=peak.tiles;bestCells=peak.cells;bestInput=peak.input;
        }
    }
    return best;
}

// Used once, only for the old short second wave; not once per candidate.
static inline GridPeak ExistingPeak(const Plan& p){
    GridPeak peak{};
    for(int group=0;group<p.blocks;++group){
        uint64_t tiles=0,cells=0,input=0;
        for(int task=group;task<p.tasks;task+=p.blocks){
            const int slot=task%(p.pM*p.pN),ms=slot/p.pN,ns=slot%p.pN;
            const int mt0=ms*p.mTiles/p.pM,mt1=(ms+1)*p.mTiles/p.pM;
            const int nt0=ns*p.nTiles/p.pN,nt1=(ns+1)*p.nTiles/p.pN;
            const int mr=bmms83::MinH(mt1*AM,p.M)-mt0*AM;
            const int nr=bmms83::MinH(nt1*BN,p.N)-nt0*BN;
            tiles+=uint64_t(mt1-mt0)*(nt1-nt0);cells+=uint64_t(mr)*nr;
            input+=uint64_t(mr)*(nt1-nt0)+uint64_t(nr)*(mt1-mt0);
        }
        if(tiles>peak.tiles)peak.tiles=tiles;if(cells>peak.cells)peak.cells=cells;
        if(input>peak.input)peak.input=input;
    }
    return peak;
}
static inline Plan MakeR11Plan(int32_t B,int32_t M,int32_t N,int32_t K,int32_t cores){
    Plan p=MakeR10Plan(B,M,N,K,cores);
    // Preserve every R10 decision. Only remove an old, incomplete second wave.
    if(cores<1||cores>64||B>cores||cores%B||p.blocks!=cores||p.tasks<=cores)return p;
    const GridPeak baseline=ExistingPeak(p);
    Plan best=p;GridPeak bestPeak=baseline;
    const int grid=cores/B;
    for(int pm=1;pm<=bmms83::MinH(p.mTiles,grid);++pm){
        if(grid%pm)continue;
        const int pn=grid/pm;if(pn>p.nTiles)continue;
        Plan candidate=p;candidate.pM=pm;candidate.pN=pn;candidate.tasks=cores;
        const GridPeak peak=SingleWavePeak(candidate);
        if(8*peak.tiles>7*baseline.tiles||8*peak.cells>7*baseline.cells||
           8*peak.input>7*baseline.input)continue;
        if(peak.tiles<bestPeak.tiles||(peak.tiles==bestPeak.tiles&&
           (peak.cells<bestPeak.cells||(peak.cells==bestPeak.cells&&
           (peak.input<bestPeak.input||(peak.input==bestPeak.input&&pn<best.pN)))))){
            best=candidate;bestPeak=peak;
        }
    }
    return best;
}

// Every candidate is a single wave using at least 3/4 of the available groups.
// Candidate cost is closed form; only the original multi-wave plan is walked once.
static inline Plan MakePlan(int32_t B,int32_t M,int32_t N,int32_t K,int32_t cores){
    Plan p=MakeR11Plan(B,M,N,K,cores);
    if(cores<2||cores>64||B>cores||p.blocks!=cores)return p;
    if(p.tasks!=cores)return p;
    const GridPeak baseline=p.tasks==p.blocks?SingleWavePeak(p):ExistingPeak(p);
    Plan best=p;GridPeak bestPeak=baseline;
    const int minGroups=(3*cores+3)/4;
    for(int pm=1;pm<=bmms83::MinH(p.mTiles,(cores-1)/B);++pm){
        const int lo=bmms83::MaxH(1,bmms83::UpH(minGroups,B*pm));
        const int hi=bmms83::MinH(p.nTiles,(cores-1)/(B*pm));
        for(int pn=lo;pn<=hi;++pn){
            Plan candidate=p;candidate.pM=pm;candidate.pN=pn;
            candidate.tasks=B*pm*pn;candidate.blocks=candidate.tasks;
            const GridPeak peak=SingleWavePeak(candidate);
            if(8*peak.tiles>7*baseline.tiles||8*peak.cells>7*baseline.cells||
               8*peak.input>7*baseline.input)continue;
            if(peak.tiles<bestPeak.tiles||(peak.tiles==bestPeak.tiles&&
               (peak.cells<bestPeak.cells||(peak.cells==bestPeak.cells&&
               (peak.input<bestPeak.input||(peak.input==bestPeak.input&&
               (pn<best.pN||(pn==best.pN&&candidate.blocks>best.blocks)))))))){
                best=candidate;bestPeak=peak;
            }
        }
    }
    return best;
}
}
namespace bmms1220 {
using Plan=bmms11r2::Plan;
static inline bool Eligible(int B,int M,int N,int K,int cores){
    return B==1&&M>=1024&&N>=1024&&K>=1536&&K<2048&&cores>=2&&
        bmms11r2::Eligible(B,M,N,K,cores);
}
static inline Plan MakePlan(int B,int M,int N,int K,int cores){
    const Plan base=bmms11r2::MakePlan(B,M,N,K,cores);
    if(!Eligible(B,M,N,K,cores))return base;
    Plan p=base;p.pM=p.mTiles;p.pN=p.nTiles;
    p.tasks=p.B*p.pM*p.pN;p.blocks=bmms83::MinH(cores,p.tasks);
    // Compare actual per-core task assignments, including the original short
    // second wave and partial macro tiles. No assumption about exact shape.
    const auto a=bmms11r2::ExistingPeak(base),b=bmms11r2::ExistingPeak(p);
    if(10*b.tiles<=9*a.tiles&&b.cells<=a.cells&&b.input<=a.input)return p;
    return base;
}
static inline bool Changed(const Plan& a,const Plan& b){
    return a.pM!=b.pM||a.pN!=b.pN||a.tasks!=b.tasks||a.blocks!=b.blocks;
}
}

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

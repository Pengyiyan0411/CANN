#include <cstdint>
#include <cstdio>
#include <cassert>
namespace bmms83 {
struct NativePlan { int32_t B,M,N,K,mTiles,nTiles,pM,pN,tasks,blocks; };
inline int UpH(int a,int b){return (a+b-1)/b;}
inline int MinH(int a,int b){return a<b?a:b;}
inline int MaxH(int a,int b){return a>b?a:b;}
inline int MinI(int a,int b){return a<b?a:b;}
}
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
static inline uint64_t RingBytes(const Plan& p){return uint64_t(p.blocks)*2*MACRO_ELEMS*4ULL;}
static inline uint64_t PartialBytes(const Plan& p){return uint64_t(p.B)*p.pN*p.M*4ULL;}
static inline uint64_t WorkspaceBytes(const Plan& p){return RingBytes(p)+PartialBytes(p);}

}
int main(){
 printf("cores,M,N,TA,pM,pN,mTiles,nTiles,tasks,blocks,peak_tiles,peak_cells,min_mtiles_per_task,max_mtiles_per_task\n");
 for(int cores=1;cores<=64;++cores)
 for(int M=1280;M<1536;M+=16)
 for(int N=4096;N<6144;N+=64)
 for(int ta=0;ta<2;++ta){
   const int K=1536;
   if(!bmms11r2::Eligible(1,M,N,K,cores))continue;
   if(ta && M%64)continue; // AlignedPitch with TB=false; N%64 already holds.
   auto p=bmms11r2::MakePlan(1,M,N,K,cores);
   auto peak=bmms11r2::ExistingPeak(p);
   auto flat=(p.mTiles*p.nTiles+cores-1)/cores;
   if(p.pN!=2||p.pM<8||p.tasks!=cores||p.blocks!=cores||flat!=peak.tiles)continue;
   int minM=100,maxM=0;
   for(int task=0;task<p.tasks;++task){
     int ms=task/p.pN;
     int span=(ms+1)*p.mTiles/p.pM-ms*p.mTiles/p.pM;
     if(span<minM)minM=span;if(span>maxM)maxM=span;
   }
   printf("%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%llu,%llu,%d,%d\n",cores,M,N,ta,
       p.pM,p.pN,p.mTiles,p.nTiles,p.tasks,p.blocks,
       (unsigned long long)peak.tiles,(unsigned long long)peak.cells,minM,maxM);
 }
}

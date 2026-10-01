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


namespace bmms11r2{static inline uint64_t RingBytes(const Plan& p){return uint64_t(p.blocks)*2*MACRO_ELEMS*4ULL;}
static inline uint64_t PartialBytes(const Plan& p){return uint64_t(p.B)*p.pN*p.M*4ULL;}
static inline uint64_t WorkspaceBytes(const Plan& p){return RingBytes(p)+PartialBytes(p);}

}
namespace bmms1219 {
using CubePlan=bmms11r2::Plan;
using bmms83::MinI;
constexpr int32_t TM=bmms11r2::TM,TN=bmms11r2::TN;
constexpr int32_t AM=bmms11r2::AM,BN=bmms11r2::BN;
constexpr int32_t MACRO_ELEMS=bmms11r2::MACRO_ELEMS;
constexpr uint16_t READY=bmms11r2::READY,FREE=bmms11r2::FREE;
// Separate from the ring (4..7) and SyncAll's reserved flags (11..14).
constexpr uint16_t PACK_ALL=0,PACK_TO_CUBE=2;
constexpr int32_t PACK_SLOT_ELEMS=32768; // 64 KiB, half-sized raw words
constexpr int32_t PACK_SLOTS=2;
constexpr uint64_t MAX_WORKSPACE_BYTES=128ULL*1024ULL*1024ULL;
constexpr uint64_t UB_BUDGET_BYTES=190ULL*1024ULL;

struct PackDesc {
    int32_t srcRows,srcCols,dstRows,dstCols,rowsPerJob,jobs;
};
struct RaggedPlan {
    CubePlan cube;
    int32_t realM,realN,realK;
    PackDesc a,b;
};

// BMMS1219_HOST_MODEL_BEGIN
static inline int32_t AlignUp(int32_t x,int32_t a){return (x+a-1)/a*a;}
static inline PackDesc MakePackDesc(int32_t sr,int32_t sc,int32_t dr,int32_t dc){
    PackDesc d{};d.srcRows=sr;d.srcCols=sc;d.dstRows=dr;d.dstCols=dc;
    d.rowsPerJob=PACK_SLOT_ELEMS/128;
    d.jobs=((dr+d.rowsPerJob-1)/d.rowsPerJob)*((dc+127)/128);
    return d;
}
static inline bool Eligible(int32_t B,int32_t M,int32_t N,int32_t K,
    int32_t dtype,int32_t cores){
    // A metadata domain, not a hidden test ID. Exact dimensions/residues are
    // NOT assumed: all valid values and all four layouts in this domain work.
    return B==1&&(dtype==1||dtype==2)&&cores>=1&&cores<=64&&
        M>=1024&&M<2048&&N>=1024&&N<2048&&K>1024&&K<1280&&
        K%8==0&&((M%16)!=0||(N%16)!=0||(K%32)!=0);
}
static inline RaggedPlan MakePlan(int32_t M,int32_t N,int32_t K,
    int32_t cores,bool ta,bool tb){
    RaggedPlan p{};p.realM=M;p.realN=N;p.realK=K;
    const int mp=AlignUp(M,16),np=AlignUp(N,16),kp=AlignUp(K,32);
    p.cube=bmms11r2::MakePlan(1,mp,np,kp,cores);
    // Describe physical ND input and its padded NZ storage. Raw words remain unchanged.
    p.a=ta?MakePackDesc(K,M,kp,mp):MakePackDesc(M,K,mp,kp);
    p.b=tb?MakePackDesc(N,K,np,kp):MakePackDesc(K,N,kp,np);
    return p;
}
static inline uint64_t ABytes(const RaggedPlan& p){return uint64_t(p.cube.M)*p.cube.K*2ULL;}
static inline uint64_t BBytes(const RaggedPlan& p){return uint64_t(p.cube.K)*p.cube.N*2ULL;}
static inline uint64_t RingBytes(const RaggedPlan& p){return bmms11r2::RingBytes(p.cube);}
static inline uint64_t PartialBytes(const RaggedPlan& p){return bmms11r2::PartialBytes(p.cube);}
static inline uint64_t WorkspaceBytes(const RaggedPlan& p){
    return ABytes(p)+BBytes(p)+RingBytes(p)+PartialBytes(p);
}
static inline uint64_t AppUbBytes(const RaggedPlan& p){
    // Two input pack buffers + the inherited consumer's explicit allocations.
    return uint64_t(PACK_SLOTS)*PACK_SLOT_ELEMS*2ULL+
        2ULL*(TM/2)*TN*4ULL+32ULL+(TM/2)*4ULL+AM*4ULL+
        3ULL*p.cube.M*4ULL;
}
// Measured dispatch policy, not an API validity requirement. Preserve the
// R43 path when the important ND source pitches already align to 128 bytes.
static inline bool PreferNz(const CubePlan& p,bool ta,bool tb){
    return (ta&&(p.M%64)!=0)||(((tb?p.K:p.N)%64)!=0);
}
static inline bool ValidPlan(const RaggedPlan& p,int32_t cores){
    const auto& c=p.cube;
    return c.B==1&&c.M%16==0&&c.N%16==0&&c.K%32==0&&
        c.M>=p.realM&&c.N>=p.realN&&c.K>=p.realK&&
        c.M<=2048&&c.N<=2048&&c.K<=1280&&
        c.pM>=1&&c.pM<=c.mTiles&&c.pN>=1&&c.pN<=c.nTiles&&
        c.tasks==c.pM*c.pN&&c.blocks>=1&&c.blocks<=cores&&c.blocks<=c.tasks&&
        p.a.rowsPerJob>=1&&p.b.rowsPerJob>=1&&p.a.jobs>=1&&p.b.jobs>=1&&
        WorkspaceBytes(p)<=MAX_WORKSPACE_BYTES&&AppUbBytes(p)<=UB_BUDGET_BYTES;
}
}
namespace bmms1222 {
using Plan=bmms1219::RaggedPlan;
static inline bool Eligible(int B,int M,int N,int K,int dtype,int cores){
    return B==1&&M>=1024&&M<2048&&N>=2048&&N<=8192&&K>=1536&&K<4096&&
      (dtype==1||dtype==2)&&bmms11r2::Eligible(B,M,N,K,cores);
}
static inline bool Prefer(int M,int N,int K,bool ta,bool tb){
    // Same physical ND-pitch criterion as accepted r19. Packing is not free:
    // preserve R06 when both expensive conversion pitches are 128B aligned.
    return (ta&&M%64!=0)||((tb?K:N)%64!=0);
}
static inline bool ValidPlan(const Plan& p,int cores){
    const auto& c=p.cube;
    return c.B==1&&c.M==p.realM&&c.N==p.realN&&c.K==p.realK&&
      c.M>=1024&&c.M<2048&&c.N>=2048&&c.N<=8192&&c.K>=1536&&c.K<4096&&
      c.M%16==0&&c.N%16==0&&c.K%32==0&&
      c.pM>=1&&c.pM<=c.mTiles&&c.pN>=1&&c.pN<=c.nTiles&&
      c.tasks==c.pM*c.pN&&c.blocks>=1&&c.blocks<=cores&&c.blocks<=c.tasks&&
      bmms1219::WorkspaceBytes(p)<=bmms1219::MAX_WORKSPACE_BYTES&&
      bmms1219::AppUbBytes(p)<=bmms1219::UB_BUDGET_BYTES;
}
}

namespace bmms1224 {
using Plan=bmms1219::RaggedPlan;
static inline bool Eligible(int B,int M,int N,int K,int dtype,int cores){
    return B==1&&M>=1024&&M<2048&&N>=2048&&N<=8192&&K>=1536&&K<4096&&
      (dtype==1||dtype==2)&&bmms11r2::Eligible(B,M,N,K,cores);
}
static inline bool Prefer(int M,int N,int K,bool ta,bool tb){
    // Same physical ND-pitch criterion as accepted r19. Packing is not free:
    // preserve R06 when both expensive conversion pitches are 128B aligned.
    return (ta&&M%64!=0)||((tb?K:N)%64!=0);
}
static inline bool ValidPlan(const Plan& p,int cores){
    const auto& c=p.cube;
    return c.B==1&&c.M==p.realM&&c.N==p.realN&&c.K==p.realK&&
      c.M>=1024&&c.M<2048&&c.N>=2048&&c.N<=8192&&c.K>=1536&&c.K<4096&&
      c.M%16==0&&c.N%16==0&&c.K%32==0&&
      c.pM>=1&&c.pM<=c.mTiles&&c.pN>=1&&c.pN<=c.nTiles&&
      c.tasks==c.pM*c.pN&&c.blocks>=1&&c.blocks<=cores&&c.blocks<=c.tasks&&
      bmms1219::WorkspaceBytes(p)<=bmms1219::MAX_WORKSPACE_BYTES&&
      bmms1219::AppUbBytes(p)<=bmms1219::UB_BUDGET_BYTES;
}
static inline bmms11r2::Plan StressPlan(const Plan& p){
    auto q=p.cube;q.pM=1;q.pN=1;q.tasks=q.B;q.blocks=1;return q;
}
}

void need(bool b){if(!b)throw std::runtime_error("r24 host invariant");}
int main(){
 int checks=0,hits=0;
 for(int B:{1,2})for(int M:{1008,1024,1040,1152,1168,1536,2032,2048})
 for(int N:{2032,2048,2064,3072,3088,8192,8208})
 for(int K:{1504,1536,1568,1632,1760,1792,2048,2176,2208,4064,4096})
 for(int dt:{0,1,2,3})for(int cores:{1,20,64})for(int layout=0;layout<4;++layout){
  bool e=bmms1224::Eligible(B,M,N,K,dt,cores);
  need(e==bmms1222::Eligible(B,M,N,K,dt,cores));
  bool pref=bmms1224::Prefer(M,N,K,layout/2,layout%2);
  need(pref==bmms1222::Prefer(M,N,K,layout/2,layout%2));++checks;
  if(!e)continue;
  auto p=bmms1219::MakePlan(M,N,K,cores,layout/2,layout%2);
  need(bmms1224::ValidPlan(p,cores)==bmms1222::ValidPlan(p,cores));
  if(pref||!bmms1224::ValidPlan(p,cores))continue;
  auto q=bmms1224::StressPlan(p);
  need(q.B==1&&q.M==M&&q.N==N&&q.K==K&&q.pM==1&&q.pN==1&&q.tasks==1&&q.blocks==1);
  need(q.mTiles==p.cube.mTiles&&q.nTiles==p.cube.nTiles);
  uint64_t begin=bmms1219::ABytes(p)+bmms1219::BBytes(p);
  need(begin%32==0&&bmms11r2::RingBytes(q)%32==0);
  need(begin+bmms11r2::WorkspaceBytes(q)<=bmms1219::WorkspaceBytes(p));
  int64_t cells=0;
  // One group covers every output cell exactly once before the reductions.
  for(int mi=0;mi<q.mTiles;++mi)for(int ni=0;ni<q.nTiles;++ni)
    cells+=int64_t(std::min(128,M-mi*128))*std::min(256,N-ni*256);
  need(cells==int64_t(M)*N);++hits;
 }
 std::cout<<"{\"guard_checks\":"<<checks<<",\"stress_plan_checks\":"<<hits<<",\"passed\":true}\n";
}

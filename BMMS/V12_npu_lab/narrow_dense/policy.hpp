// BMMS1237_PLAN_BEGIN
namespace bmms1237 {
using Plan=bmms11r2::Plan;
static inline bool InDomain(int B,int M,int N,int K){
    return B==1&&((M>=1536&&M<1792&&N>=2048&&N<3072&&K>=2048&&K<2560)||
                  (M>=1280&&M<1536&&N>=4096&&N<6144&&K>=1536&&K<1664));
}
static inline Plan MakePlan(int B,int M,int N,int K,int cores){
    const Plan old=bmms11r2::MakePlan(B,M,N,K,cores);
    if(!InDomain(B,M,N,K)||cores<2||cores>64)return old;
    const auto prior=bmms11r2::ExistingPeak(old);
    Plan best=old;auto peakBest=prior;
    const int minGroups=(3*cores+3)/4;
    for(int pm=1;pm<=bmms83::MinH(old.mTiles,cores);++pm){
        const int lo=bmms83::MaxH(1,bmms83::UpH(minGroups,pm));
        const int hi=bmms83::MinH(old.nTiles,cores/pm);
        for(int pn=lo;pn<=hi;++pn){
            Plan p=old;p.pM=pm;p.pN=pn;p.tasks=pm*pn;p.blocks=p.tasks;
            const auto q=bmms11r2::SingleWavePeak(p);
            // Strictly reduce peak macro count without increasing peak cells/input.
            // Unlike R14, evaluate this also when the old plan has a partial 2nd wave.
            if(q.tiles>=prior.tiles||q.cells>prior.cells||q.input>prior.input)continue;
            if(q.tiles<peakBest.tiles||(q.tiles==peakBest.tiles&&
               (q.cells<peakBest.cells||(q.cells==peakBest.cells&&
               (q.input<peakBest.input||(q.input==peakBest.input&&
               (pn<best.pN||(pn==best.pN&&p.blocks>best.blocks)))))))){
                best=p;peakBest=q;
            }
        }
    }
    return best;
}
}
// BMMS1237_PLAN_END

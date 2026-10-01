
namespace c12lab {
using Plan=bmms11r2::Plan;
static inline bool Eligible(int B,int M,int N,int K,int cores){
 return B==1&&M>=1024&&N>=1024&&K>=1536&&K<2048&&cores>=2&&bmms11r2::Eligible(B,M,N,K,cores);
}
static inline Plan PacketPlan(Plan p,int cores,int packetN){
 p.pM=p.mTiles;p.pN=(p.nTiles+packetN-1)/packetN;
 p.tasks=p.B*p.pM*p.pN;p.blocks=bmms83::MinH(cores,p.tasks);return p;
}
}

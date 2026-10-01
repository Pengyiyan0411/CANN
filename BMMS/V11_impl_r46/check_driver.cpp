#include "cpu_shim.hpp"
#include "tiling_stub.hpp"
#include "extracted.hpp"
#include <array>
#include <iostream>
#include <random>
#include <sstream>

namespace f=bmms_c8f46;
namespace old=bmmmaxsum_v43;
static int runs=0,planChecks=0,guardChecks=0,tilingChecks=0;
static std::vector<std::array<int,9>> examples;

template<class Fn>void workers(int n,Mock::Context& ctx,Fn fn,bool reverse){
    std::mutex mu;std::string error;std::vector<std::thread> ts;
    for(int ix=0;ix<n;++ix){const int w=reverse?n-1-ix:ix;
        ts.emplace_back([&,w]{Mock::worker=Mock::logical=w;Mock::ctx=&ctx;
            try{fn();}catch(const std::exception& e){
                std::lock_guard lock(mu);if(error.empty())error=e.what();ctx.barrier.cancel();
            }
        });
    }
    for(auto& t:ts)t.join();
    Mock::ctx=&ctx;
    if(!error.empty())throw std::runtime_error(error);
}

static void geometry(const f::MainTailPlan& q,int cores){
    Mock::need(f::ValidPlan(q,cores),"invalid selected plan");
    auto p=q.grid;
    Mock::need(p.tasks==p.workers,"B1 unexpectedly oversubscribes workers");
    int mEnd=0;
    for(int ms=0;ms<p.pM;++ms){
        int start=(ms*p.mTiles/p.pM)*p.tileM;
        int end=std::min(p.M,((ms+1)*p.mTiles/p.pM)*p.tileM);
        Mock::need(start==mEnd&&end>start,"M coverage/empty shard");mEnd=end;
        Mock::need(end-start<=p.mPitch,"M bound");
        // (ns+ms)%pN must remain a permutation, including the tail owner.
        std::vector<int> owners(p.pN);
        for(int ns=0;ns<p.pN;++ns)++owners[(ns+ms)%p.pN];
        for(int count:owners)Mock::need(count==1,"N task owner collision");
    }
    Mock::need(mEnd==p.M,"lost M tail");
    std::vector<int> cover(q.realN);
    for(int ns=0;ns<p.pN;++ns){
        int first=ns*p.nTiles/p.pN,last=(ns+1)*p.nTiles/p.pN;
        int cols=(last-first)*p.vecN;
        int start=std::min(first*p.vecN,q.realN-cols),end=start+cols;
        Mock::need(start>=0&&end<=q.realN,"N window outside real columns");
        Mock::need(cols%p.vecN==0&&cols>0,"partial N tile");
        for(int j=start;j<end;++j)++cover[j];
    }
    int duplicates=0;
    for(int count:cover){Mock::need(count==1||count==2,"N hole or excessive overlap");duplicates+=count-1;}
    Mock::need(duplicates==p.N-q.realN,"wrong overlap extent");
    // Verify last address of every physical submatrix for all layouts.
    for(bool ta:{false,true})for(bool tb:{false,true}){
        for(int ms=0;ms<p.pM;++ms){
            int m0=(ms*p.mTiles/p.pM)*p.tileM;
            int rows=std::min(p.M,((ms+1)*p.mTiles/p.pM)*p.tileM)-m0;
            int64_t ao=ta?m0:int64_t(m0)*p.K;
            int64_t lastA=ao+(ta?int64_t(p.K-1)*p.M+rows-1:int64_t(rows-1)*p.K+p.K-1);
            Mock::need(lastA<int64_t(p.M)*p.K,"A extent");
            for(int ns=0;ns<p.pN;++ns){
                int first=ns*p.nTiles/p.pN,last=(ns+1)*p.nTiles/p.pN;
                int cols=(last-first)*p.vecN;
                int n0=std::min(first*p.vecN,q.realN-cols);
                int64_t bo=tb?int64_t(n0)*p.K:n0;
                int64_t lastB=bo+(tb?int64_t(cols-1)*p.K+p.K-1:int64_t(p.K-1)*q.realN+cols-1);
                Mock::need(lastB<int64_t(p.K)*q.realN,"B extent");
            }
        }
    }
    Mock::need(old::FastAppUbBytes(p)<=97*1024,"UB overflow");
    ++planChecks;
}

static void host_checks(){
    // Boundary sets include each nonzero N residue modulo 16, both ends of
    // the route domain, every tile-width boundary, and non-power-of-two cores.
    std::vector<int> ns{1025,1039,1041,1087,1089,1151,1153,1279,1281,1535,1537,1791,1793,2031,2047};
    for(int r=1;r<16;++r)ns.push_back(1280+r);
    for(int m:{1024,1025,1087,1152,1281,1793,2047})
        for(int n:ns)for(int k:{1032,1040,1048,1152,1272})for(int c:{2,3,4,8,20,32,64}){
            auto q=f::MakePlan(m,n,k,c);geometry(q,c);
        }
    for(int n:{1025,1087,1153,1281,1537,2047}){
        auto q=f::MakePlan(1153,n,1160,20);auto p=q.grid;
        examples.push_back({p.M,n,p.K,p.tileM,p.vecN,p.pM,p.pN,p.workers,p.N});
    }
    for(int B:{1,2,64})for(int M:{32,127,1023,1024,1025,2047,2048})
        for(int N:{32,240,1023,1024,1025,2032,2047,2048})
        for(int K:{32,128,256,504,1024,1032,1152,1272,1280,4096,8192})
        for(int d:{0,1,2,3})for(int c:{0,1,20,64,65}){
            bool expected=B==1&&(d==1||d==2)&&c>=1&&c<=64&&
                M>=1024&&M<2048&&N>=1024&&N<2048&&N%16!=0&&
                K>1024&&K<1280&&K%8==0;
            Mock::need(f::Eligible(B,M,N,K,d,c)==expected,"guard widened");++guardChecks;
        }
    auto q=f::MakePlan(1153,1293,1160,20);
    for(int d:{1,2})for(bool ta:{false,true})for(bool tb:{false,true}){
        TCubeTiling td{};matmul_tiling::reject=0;
        Mock::need(f::GetTiling(q,d,ta,tb,td),"mock tiling rejected");
        auto r=matmul_tiling::record;
        Mock::need(r.N==q.realN&&r.N!=q.grid.N&&r.M==q.grid.M&&r.K==q.grid.K,"physical host stride");
        Mock::need(r.ta==ta&&r.tb==tb&&r.vec&&r.traverse&&r.ub==64*1024,"tiling type/space");
        Mock::need(r.dim==q.grid.workers&&r.bm==q.grid.tileM&&r.bn==q.grid.vecN,"tiling dimensions");
        for(int bad=1;bad<=10;++bad){
            matmul_tiling::reject=bad;
            Mock::need(!f::GetTiling(q,d,ta,tb,td),"unsupported SDK metadata accepted");++tilingChecks;
        }
        ++tilingChecks;
    }
    matmul_tiling::reject=0;
    // Grouped streams with more than one tile on both axes are accepted only
    // when the actual ordering is flat M-inner; bad FIRSTM/grouped variants fail.
    auto p=old::BuildPlan(1,257,256,40,1,16,16,1,1);
    TCubeTiling td{};td.stepM=1;td.stepN=1;td.iterateOrder=1;
    Mock::need(!f::ValidStream(p,td),"grouped M stream accepted");
    td.stepM=p.mTiles;Mock::need(f::ValidStream(p,td),"flat stream rejected");
    td.iterateOrder=0;Mock::need(!f::ValidStream(p,td),"N-inner stream accepted");
    tilingChecks+=3;
    p=old::BuildPlan(1,65,48,40,2,16,16,1,2);
    td.stepM=1;td.stepN=1;td.iterateOrder=0;
    Mock::need(old::FlatFastStream(p,td)&&!f::ValidStream(p,td),"ceil N stream guard missed");
    ++tilingChecks;
    auto one=f::MakePlan(1153,1293,1160,1);
    Mock::need(!f::ValidPlan(one,1),"one core must return to R43");
}

struct Fixture{int M,N,K,tm,vn,pm,pn;};
static const std::vector<Fixture> fixtures={
    {17,17,32,16,16,1,1}, {31,33,40,16,16,2,2},
    {33,49,32,16,16,3,3}, {65,79,40,32,16,2,2},
    {79,97,32,32,32,3,3}, {65,143,72,32,32,2,2},
    {33,129,40,32,64,1,2}, {79,191,32,32,64,3,2},
    {65,255,32,32,128,2,1}, {129,257,40,64,128,3,2},
    {33,511,32,32,256,1,1}, {145,287,32,64,64,2,2},
    {17,127,72,16,32,2,3}, {49,95,40,16,16,3,5},
    {129,529,32,128,128,2,2}, {65,543,32,64,256,2,2}
};

template<class T,bool TA,bool TB>
static void numeric(const Fixture& z,int pattern,bool reverse,int order=1){
    const int M=z.M,N=z.N,K=z.K,pn=std::max(2,z.pn),cores=z.pm*pn;
    f::MainTailPlan q{old::BuildPlan(1,M,old::CeilDiv(N,z.vn)*z.vn,K,cores,z.tm,z.vn,z.pm,pn),N};
    Mock::need(f::ValidPlan(q,cores),"invalid fixture");
    auto p=q.grid;
    std::vector<T>a(M*K),b(N*K);std::vector<float> y(1,NAN),part(old::PartialBytes(p)/4,NAN);
    auto ai=[&](int m,int k){return TA?k*M+m:m*K+k;};
    auto bi=[&](int k,int n){return TB?n*K+k:k*N+n;};
    std::mt19937 rng(98473+M*3+N*5+K*7+pattern);
    for(int m=0;m<M;++m)for(int k=0;k<K;++k){
        float v=float(int(rng()%17)-8)/8;
        if(pattern==1||pattern==2||pattern==3)v=float((m+k)%7+1)/8;
        if(pattern==4)v=0;
        if(pattern==5)v=(m%2?-1.0f:1.0f)/8;
        a[ai(m,k)]=T(v);
    }
    for(int k=0;k<K;++k)for(int n=0;n<N;++n){
        float v=float(int(rng()%17)-8)/8;
        if(pattern==1)v=-float((k+n)%7+1)/8; // all true C values negative
        if(pattern==2)v=n==N-1?2.0f:-1.0f; // only tail has the row winner
        if(pattern==3)v=n==N-z.vn?2.0f:-1.0f; // overlap repeated max
        if(pattern==4)v=0;
        if(pattern==5)v=(k%2?-1.0f:1.0f); // exact cancellation in K
        b[bi(k,n)]=T(v);
    }
    double gold=0;
    for(int m=0;m<M;++m){
        double row=-INFINITY;
        for(int n=0;n<N;++n){
            double sum=0;for(int k=0;k<K;++k)sum+=double(float(a[ai(m,k)]))*float(b[bi(k,n)]);
            row=std::max(row,sum);
        }
        gold+=row;
    }
    TCubeTiling td{};td.baseM=p.tileM;td.baseN=p.vecN;td.baseK=32;
    td.singleCoreM=p.mPitch;td.singleCoreN=p.nPitch;td.singleCoreK=K;
    td.stepM=old::CeilDiv(p.mTiles,p.pM);td.stepN=2;td.iterateOrder=order;
    Mock::need(f::ValidStream(p,td),"fixture stream is not flat");
    Mock::Context ctx(p.workers);ctx.add(a.data(),a.size()*sizeof(T),true);
    ctx.add(b.data(),b.size()*sizeof(T),true);ctx.add(y.data(),4,false);
    if(!part.empty())ctx.add(part.data(),part.size()*4,false);
    try{
        workers(p.workers,ctx,[&]{
            AscendC::TPipe pipe;f::FastFusedDevice<T,TA,TB> op;
            op.tiling=td;op.mm.Init(&td,&pipe);
            op.Init(reinterpret_cast<GM_ADDR>(a.data()),reinterpret_cast<GM_ADDR>(b.data()),
                reinterpret_cast<GM_ADDR>(y.data()),reinterpret_cast<GM_ADDR>(part.data()),q,&pipe);
            op.Process();
        },reverse);
        Mock::need(std::isfinite(y[0])&&double(y[0])==gold,"numerical mismatch");
        ++runs;
    }catch(const std::exception&e){
        std::ostringstream s;s<<"M="<<M<<" N="<<N<<" K="<<K<<" tile="<<z.tm<<"x"<<z.vn
            <<" grid="<<z.pm<<"x"<<z.pn<<" dtype="<<(std::is_same_v<T,half>?"FP16":"BF16")
            <<" ta="<<TA<<" tb="<<TB<<" pattern="<<pattern<<" reverse="<<reverse<<": "<<e.what();
        throw std::runtime_error(s.str());
    }
}

template<class T>static void all_layouts(const Fixture& z,int pattern,bool reverse,int order=1){
    numeric<T,false,false>(z,pattern,reverse,order);
    numeric<T,false,true>(z,pattern,reverse,order);
    numeric<T,true,false>(z,pattern,reverse,order);
    numeric<T,true,true>(z,pattern,reverse,order);
}

int main(){try{
#ifdef FAULT_CHECK
    // Each injected fault must be detected by an independent tail-only oracle.
    numeric<half,false,false>({31,33,40,16,16,2,2},2,false);
#else
    host_checks();
    for(const auto& z:fixtures)for(int pat=0;pat<6;++pat)for(bool reverse:{false,true}){
        all_layouts<half>(z,pat,reverse);all_layouts<bfloat16_t>(z,pat,reverse);
    }
    // Both traversal orders are legal in the single-M-tile and single-N-tile
    // cases; the uneven-shard maximum N tile count must be used in the guard.
    for(const auto& z:std::vector<Fixture>{{31,65,40,32,16,1,2},{49,17,32,16,16,1,2}})
        for(int pat:{0,1,2}){all_layouts<half>(z,pat,false,0);all_layouts<bfloat16_t>(z,pat,true,0);}
#endif
    std::cout<<"{\"numeric_runs\":"<<runs<<",\"planner_geometry_checks\":"<<planChecks
        <<",\"guard_checks\":"<<guardChecks<<",\"host_tiling_contract_checks\":"<<tilingChecks
        <<",\"exact_dyadic_oracle_mismatches\":0,\"representative_plans\":[";
    for(size_t i=0;i<examples.size();++i){if(i)std::cout<<",";std::cout<<"[";
        for(size_t j=0;j<examples[i].size();++j){if(j)std::cout<<",";std::cout<<examples[i][j];}std::cout<<"]";}
    std::cout<<"]}\n";
    return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}

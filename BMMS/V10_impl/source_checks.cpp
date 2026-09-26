// Executes source-extracted V10 logic with a CPU semantic adapter, not CANN.
#include "cpu_shim.hpp"
#include "candidate.hpp"
#include <array>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <random>
#include <sstream>

static int runs=0,pairs=0,plans=0,limits=0;
static double maxAbs=0,maxRel=0;
static uint64_t maxUB=0,maxPartial=0;
static std::map<std::string,std::vector<uint32_t>> bits;
static std::map<std::string,int> routes;
static std::vector<std::string> knownLimits;

void planner_checks() {
    for(int B:{1,2,3,7,20,64})for(int M:{1,15,16,17,63,64,65,127,128,129,513,2048,8192})
    for(int N:{1,7,8,9,63,64,80,127,128,129,1023,1024,1025,8191,8192})
    for(int cores:{1,2,3,7,20,32,64}) {
        auto p=bmms10::MakePlan(B,M,N,32,cores);
        Mock::need(bmms10::ValidPlan(p,cores),"invalid source plan");
        maxUB=std::max(maxUB,bmms10::AppUBBytes(p));
        maxPartial=std::max(maxPartial,bmms10::PartialBytes(p));
        std::vector<int> hit(B*p.mTiles*p.nTiles);
        for(int t=0;t<p.tasks;++t) {
            int batch=t/(p.pM*p.pN),ms=t%(p.pM*p.pN)/p.pN,ns=t%p.pN;
            int mb=ms*p.mTiles/p.pM,me=(ms+1)*p.mTiles/p.pM;
            int nb=ns*p.nTiles/p.pN,ne=(ns+1)*p.nTiles/p.pN;
            Mock::need(me>mb&&ne>nb,"empty shard");
            for(int m=mb;m<me;++m)for(int n=nb;n<ne;++n)++hit[(batch*p.mTiles+m)*p.nTiles+n];
        }
        for(int h:hit)Mock::need(h==1,"missing or repeated C tile ownership");
        if(p.pN>1)Mock::need(B*p.mTiles<cores&&N>=1024&&p.pM==p.mTiles&&p.pN<=p.nTiles/2,"Split-N guard");
        if(!BMMS10_SPLIT_N)Mock::need(p.pN==1,"F01 split N");
        if(B>=cores)Mock::need(p.direct,"batch parallel path unexpectedly split");
        ++plans;
    }
}

template<class Fn>void workers(int n,Mock::Context& ctx,Fn fn,bool reverse) {
    std::vector<std::thread> threads; std::mutex mu; std::string error;
    for(int i=0;i<n;++i) {
        const int w=reverse?n-1-i:i;
        threads.emplace_back([&,w]{Mock::worker=w;Mock::logical=w;Mock::ctx=&ctx;
            try {fn();}catch(const std::exception& e){std::lock_guard lock(mu);if(error.empty())error=e.what();ctx.barrier.cancel();}
        });
    }
    for(auto& t:threads)t.join();
    if(!error.empty())throw std::runtime_error(error);
    Mock::ctx=&ctx;
}

template<class T,bool TA,bool TB>
void one(int B,int M,int N,int K,int cores,int pattern,bool reverse) {
    auto p=bmms10::MakePlan(B,M,N,K,cores);
    std::string key=(std::is_same_v<T,half>?"f16":"b16")+std::string(TA?"_t":"_n")+(TB?"t":"n")+
        "_"+std::to_string(B)+"_"+std::to_string(M)+"_"+std::to_string(N)+"_"+std::to_string(K)+
        "_c"+std::to_string(cores)+"_p"+std::to_string(pattern);
    std::vector<T>a(int64_t(B)*M*K),b(int64_t(B)*K*N);
    std::vector<float>y(B,NAN),partial(bmms10::PartialBytes(p)/4,NAN);
    std::vector<double>gold(B);
    auto ai=[&](int z,int m,int k){return int64_t(z)*M*K+(TA?int64_t(k)*M+m:int64_t(m)*K+k);};
    auto bi=[&](int z,int k,int n){return int64_t(z)*N*K+(TB?int64_t(n)*K+k:int64_t(k)*N+n);};
    std::mt19937 rng(1301+B*11+M*17+N*31+K*3+pattern);
    std::uniform_real_distribution<float>d(-0.0625f,0.0625f);
    for(int z=0;z<B;++z)for(int m=0;m<M;++m)for(int k=0;k<K;++k) {
        float v=d(rng);if(pattern==1)v=std::abs(v);
        if(pattern==2)v=k==0?(m%2?0.25f:-0.25f):0;
        if(pattern==4)v=k==0?(m%2?-64.0f:64.0f):(k==1&&m%2==0?0.015625f:0);
        if(pattern==5)v=k<2?std::ldexp(1.0f,64):0;
        a[ai(z,m,k)]=T(v);
    }
    for(int z=0;z<B;++z)for(int k=0;k<K;++k)for(int n=0;n<N;++n) {
        float v=d(rng);if(pattern==1)v=-std::abs(v);
        if(pattern==2)v=k==0?(n<N/2?-0.25f:0.25f):0;
        if(pattern==4)v=k==0?64.0f:(k==1?0.0078125f:0);
        if(pattern==5)v=k<2?std::ldexp(k==0?1.0f:-1.0f,64):0;
        b[bi(z,k,n)]=T(v);
    }
    const auto aBefore=a,bBefore=b;
    for(int z=0;z<B;++z)for(int m=0;m<M;++m) {
        double mx=-INFINITY;
        for(int n=0;n<N;++n) {double sum=0;for(int k=0;k<K;++k)sum+=double(float(a[ai(z,m,k)]))*double(float(b[bi(z,k,n)]));mx=std::max(mx,sum);}
        gold[z]+=mx;
    }
    Mock::Context ctx(p.blocks);ctx.add(a.data(),a.size()*sizeof(T),true);ctx.add(b.data(),b.size()*sizeof(T),true);
    ctx.add(y.data(),y.size()*4,false);if(!partial.empty())ctx.add(partial.data(),partial.size()*4,false);
    TCubeTiling td;td.baseM=p.tileM;td.baseN=p.tileN;td.baseK=128;
    td.singleCoreM=std::min(p.tileM,M);td.singleCoreN=std::min(N,p.maxNTiles*p.tileN);td.singleCoreK=K;
    // Vary grouped traversal independently; one M base tile makes both orders safe.
    td.iterateOrder=reverse?0:1;td.stepM=reverse?3:1;td.stepN=reverse?2:1;
    try {
        workers(p.blocks,ctx,[&]{AscendC::TPipe pipe;bmms10::StreamingDevice<T,TA,TB> op;
            op.mm.Init(&td,&pipe);op.tiling=td;
            op.Init((GM_ADDR)a.data(),(GM_ADDR)b.data(),(GM_ADDR)y.data(),(GM_ADDR)partial.data(),p,&pipe);
            Mock::need(pipe.allocated==bmms10::AppUBBytes(p),"host/device UB accounting differs");
            op.Process();
        },reverse);
        Mock::need(std::memcmp(a.data(),aBefore.data(),a.size()*sizeof(T))==0,"A mutated");
        Mock::need(std::memcmp(b.data(),bBefore.data(),b.size()*sizeof(T))==0,"B mutated");
        std::vector<uint32_t> outBits;bool failed=false;
        for(int z=0;z<B;++z) {
            Mock::need(ctx.locate((uintptr_t)(y.data()+z),4)->writer[z].load()>=0,"y not written");
            double ref=float(gold[z]),err=std::abs(double(y[z])-ref),rel=ref==0?(err==0?0:INFINITY):err/std::abs(ref);
            bool ok=std::isfinite(y[z])&&err<1e-4&&rel<1e-4;
            if(pattern>=4){if(!ok)failed=true;continue;}
            if(!ok){std::ostringstream s;s<<key<<" actual "<<y[z]<<" ref "<<ref<<" abs "<<err<<" rel "<<rel;throw std::runtime_error(s.str());}
            maxAbs=std::max(maxAbs,err);maxRel=std::max(maxRel,rel);outBits.push_back(std::bit_cast<uint32_t>(y[z]));
        }
        if(pattern>=4){Mock::need(failed,"expected FP32 limitation no longer reproduced; review test");++limits;knownLimits.push_back(key);return;}
        if(bits.count(key)){Mock::need(bits.at(key)==outBits,"repeated invocation changed output bits");++pairs;}else bits[key]=outBits;
        ++runs;++routes[p.pN>1?"split_n":(p.direct?"batch_direct":"split_m")];
    }catch(const std::exception& e){throw std::runtime_error(key+": "+e.what());}
}

template<class T>void layouts(const std::array<int,5>& s,int pat,bool rev) {
    auto [b,m,n,k,c]=s;
    one<T,false,false>(b,m,n,k,c,pat,rev);one<T,false,true>(b,m,n,k,c,pat,rev);
    one<T,true,false>(b,m,n,k,c,pat,rev);one<T,true,true>(b,m,n,k,c,pat,rev);
}

int main(){try {
    planner_checks();
    const std::vector<std::array<int,5>> shapes={
        {1,1,1,32,20},{3,3,5,40,20},{2,17,19,72,3},{1,65,137,136,7},
        {3,129,255,64,4},{1,127,80,128,4},{1,129,1023,32,8},{1,16,1024,32,8},
        {1,16,1025,40,8},{1,80,1537,32,7},{1,1,8192,32,20},{64,1,17,32,20},
        {7,129,33,32,2},{1,8192,1,32,20},{1,3,5,8192,3},{1,513,17,256,1},
        {1,257,129,32,3},{1,64,128,32,1},{2,67,132,40,5},{5,31,1025,32,3},
        {3,16,1024,32,20},{1,17,8191,32,8}};
    const std::vector<std::array<int,5>> edge={
        {1,17,19,40,3},{1,65,137,72,7},{1,17,1025,32,8},{1,80,1537,32,7},{3,129,80,32,2}};
    for(int rev=0;rev<2;++rev) {
        for(auto s:shapes){layouts<half>(s,0,rev);layouts<bfloat16_t>(s,0,rev);}
        for(auto s:edge)for(int pat:{1,2}){layouts<half>(s,pat,rev);layouts<bfloat16_t>(s,pat,rev);}
    }
    one<half,false,false>(1,2,1,32,20,4,false);
    one<bfloat16_t,false,false>(1,2,1,32,20,4,false);
    one<bfloat16_t,false,false>(1,2,1,32,20,5,false);
    std::cout<<std::setprecision(12)<<"{\"ordinary_source_runs\":"<<runs<<",\"bitwise_repeat_pairs\":"<<pairs
        <<",\"plan_checks\":"<<plans<<",\"max_application_ub_bytes\":"<<maxUB<<",\"max_partial_bytes\":"<<maxPartial
        <<",\"ordinary_strict_misses\":0,\"max_abs\":"<<maxAbs<<",\"max_rel\":"<<maxRel
        <<",\"known_precision_limitations_reproduced\":"<<limits<<",\"routes\":{";
    bool first=true;for(auto& [key,v]:routes){if(!first)std::cout<<",";first=false;std::cout<<"\""<<key<<"\":"<<v;}
    std::cout<<"},\"known_limit_cases\":[";
    for(size_t i=0;i<knownLimits.size();++i){if(i)std::cout<<",";std::cout<<"\""<<knownLimits[i]<<"\"";}
    std::cout<<"],\"output_bits\":{";first=true;
    for(auto& [key,v]:bits){if(!first)std::cout<<",";first=false;std::cout<<"\""<<key<<"\":[";
        for(size_t i=0;i<v.size();++i){if(i)std::cout<<",";std::cout<<v[i];}std::cout<<"]";}
    std::cout<<"},\"cann_compiled\":false,\"npu_tested\":false,\"full_domain_precision_accepted\":false}\n";
    return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}

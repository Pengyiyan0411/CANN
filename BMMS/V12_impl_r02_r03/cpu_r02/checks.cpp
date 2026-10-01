#define BMMS9_CPU_TEST 1
#define BMMS11_CPU_TEST 1
#define BMMS11R2_CPU_TEST 1
#include "cube_model.hpp"
#include "common_extracted.hpp"
#include "ring_extracted.hpp"
#include "extracted.hpp"
#include <iostream>
#include <random>
#include <map>
#include <sstream>
using Plan=bmms1202::Plan;
uint64_t oldA=0,newA=0,oldB=0,newB=0;
uint64_t runs=0,realRuns=0,duplicateBefore=0,duplicateAfter=0,reduceRows=0,reads=0,credits=0;
template<class Fn>void workers(int count,Mock::Context& ctx,Mock::Flags& flags,int aiv,Fn fn,bool reverse){
    std::mutex mutex;std::string error;std::vector<std::thread> threads;
    for(int index=0;index<count;++index){int w=reverse?count-1-index:index;
        threads.emplace_back([&,w]{try{
            Mock::ctx=&ctx;Mock::flags=&flags;Mock::worker=w;Mock::cube=w>=aiv;
            Mock::logical=Mock::cube?w-aiv:w;Mock::pairId=Mock::cube?w-aiv:w/2;Mock::subId=Mock::cube?0:w%2;
            Mock::localFlags={};Mock::smallMmadPending=false;fn(w);
            for(auto& kind:Mock::localFlags)for(int pending:kind)Mock::need(pending==0,"local credit leaked");
        }catch(const std::exception&e){std::lock_guard lock(mutex);if(error.empty())error=e.what();ctx.barrier.cancel();flags.cancel();}});
    }for(auto& t:threads)t.join();if(!error.empty())throw std::runtime_error(error);
}
float value(int z,int m,int n,int pattern){
    unsigned h=unsigned(z+1)*2654435761u+unsigned(m+3)*2246822519u+unsigned(n+5)*3266489917u;h^=h>>15;
    const float v=float(int(h%2001)-1000)/128;
    return pattern==1?-std::abs(v)-0.125f:pattern==2?0:v;
}
void publish(const Plan& p,float* ws,int pattern){
    const int g=Mock::pairId;int seq=0;AscendC::GlobalTensor<float> ring;
    ring.SetGlobalBuffer(ws,size_t(p.blocks)*2*bmms11r2::MACRO_ELEMS);
    for(int task=g;task<p.tasks;task+=p.blocks){
        const int z=task/(p.pM*p.pN),ms=task/p.pN%p.pM,ns=task%p.pN;
        for(int mt=ms*p.mTiles/p.pM;mt<(ms+1)*p.mTiles/p.pM;++mt)
          for(int nt=ns*p.nTiles/p.pN;nt<(ns+1)*p.nTiles/p.pN;++nt){
            const int slot=seq%2,m0=mt*128,n0=nt*256,ar=std::min(128,p.M-m0),br=std::min(256,p.N-n0);
            if(seq>=2)AscendC::CrossCoreWaitFlag<2>(6+slot);
            for(int mo=0;mo<ar;mo+=64)for(int no=0;no<br;no+=128){
                const int mr=std::min(64,ar-mo),nr=std::min(128,br-no);
                const size_t off=(size_t(g)*2+slot)*32768+(mo/64*2+no/128)*8192;
                RingAudit::write(ws+off,mr*nr);
                for(int r=0;r<mr;++r)for(int n=0;n<nr;++n)ring.SetValue(off+r*128+n,value(z,m0+mo+r,n0+no+n,pattern));
            }
            AscendC::CrossCoreSetFlag<2,PIPE_FIX>(4+slot);++seq;
          }
    }
    for(int i=0;i<std::min(2,seq);++i)AscendC::CrossCoreWaitFlag<2>(6+i);
}
Plan custom(int B,int M,int N,int pm,int pn,int blocks){
    Plan p{};p.B=B;p.M=M;p.N=N;p.K=1536;p.mTiles=(M+127)/128;p.nTiles=(N+255)/256;
    p.pM=std::min(pm,p.mTiles);p.pN=std::min(pn,p.nTiles);p.tasks=B*p.pM*p.pN;p.blocks=std::min(blocks,p.tasks);return p;
}
template<class T,bool TA,bool TB>std::vector<uint32_t> run(Plan p,bool compact,int pattern,bool reverse,bool real=false){
    const auto rb=bmms11r2::RingBytes(p),pb=bmms11r2::PartialBytes(p);
    std::vector<float> ws((rb+pb)/4,NAN),y(p.B,NAN);float* part=ws.data()+rb/4;
    std::vector<T>a(real?size_t(p.B)*p.M*p.K:0),b(real?size_t(p.B)*p.K*p.N:0);
    auto ai=[&](int z,int m,int k){return size_t(z)*p.M*p.K+(TA?size_t(k)*p.M+m:size_t(m)*p.K+k);};
    auto bi=[&](int z,int k,int n){return size_t(z)*p.K*p.N+(TB?size_t(n)*p.K+k:size_t(k)*p.N+n);};
    if(real){for(size_t i=0;i<a.size();++i)a[i]=T(float(int(i%13)-6)/16);for(size_t i=0;i<b.size();++i)b[i]=T(float(int(i%11)-5)/16);}
    std::vector<uint32_t> gold;
    for(int z=0;z<p.B;++z){std::vector<float> rows(p.M,-INFINITY);
        for(int m=0;m<p.M;++m)for(int n=0;n<p.N;++n){float v=value(z,m,n,pattern);
            if(real){v=0;for(int k=0;k<p.K;++k)v+=float(a[ai(z,m,k)])*float(b[bi(z,k,n)]);}
            rows[m]=std::max(rows[m],v);
        }gold.push_back(std::bit_cast<uint32_t>(AscendC::sumtree(rows)));
    }
    Mock::Context ctx(2*p.blocks);Mock::Flags flags(p.blocks);
    ctx.add(ws.data(),ws.size()*4,false);ctx.add(y.data(),y.size()*4,false);
    if(real){ctx.add(a.data(),a.size()*sizeof(T),true);ctx.add(b.data(),b.size()*sizeof(T),true);}
    RingAudit::State ring(ws.data(),p.blocks,32768);RingAudit::active=&ring;SplitAudit::active=nullptr;ReductionAudit::active=nullptr;
    TargetAudit::begin(part,pb/4);OpStats::reset();Traffic::reset();TrafficAB::begin((uintptr_t)a.data(),a.size()*sizeof(T),(uintptr_t)b.data(),b.size()*sizeof(T));
    try{
        workers(3*p.blocks,ctx,flags,2*p.blocks,[&](int){AscendC::TPipe pipe;
            if(Mock::cube){
                if(compact){bmms1202::ResidentAProducer<T,TA,TB> op;op.Init((GM_ADDR)a.data(),(GM_ADDR)b.data(),(GM_ADDR)ws.data(),p,&pipe);op.Process();}
                else{bmms11r2::ReuseProducer<T,TA,TB> op;op.Init((GM_ADDR)a.data(),(GM_ADDR)b.data(),(GM_ADDR)ws.data(),p,&pipe);op.Process();}
            }else{bmms11r2::RowMaxConsumer op;op.Init((GM_ADDR)ws.data(),(GM_ADDR)part,(GM_ADDR)y.data(),p,&pipe);op.Process();}
        },reverse);
        flags.drained();ring.drained();Mock::need(ctx.barrier.generation==1,"barrier count changed");
        Mock::need(ring.readElements==uint64_t(p.B)*p.M*p.N,"live C read count changed");
        Mock::need(TargetAudit::reads==pb/4&&TargetAudit::writes==pb/4,"partial coverage mismatch");for(auto v:TargetAudit::visits)Mock::need(v==1,"partial read coverage mismatch");
        Mock::need(OpStats::reduceRows==uint64_t(p.B)*p.M*p.nTiles,"extra row reductions");
        std::vector<uint32_t> got;for(float x:y)got.push_back(std::bit_cast<uint32_t>(x));Mock::need(got==gold,"numeric result differs from full row-max plus original sum tree");
        const uint64_t expectedA=uint64_t(p.B)*p.M*p.K*2*(compact?p.pN:p.nTiles);
        const uint64_t expectedB=uint64_t(p.B)*p.N*p.K*2*p.mTiles;
        Mock::need(TrafficAB::aBytes==expectedA&&TrafficAB::bBytes==expectedB,"operand traffic mismatch");
        Mock::need(Traffic::mmads==uint64_t(p.B)*((p.M+63)/64)*((p.N+127)/128)*((p.K+63)/64),"MMAD arithmetic changed");
        if(compact){newA+=TrafficAB::aBytes;newB+=TrafficAB::bBytes;}else{oldA+=TrafficAB::aBytes;oldB+=TrafficAB::bBytes;}
        reduceRows+=OpStats::reduceRows;reads+=ring.readElements;credits+=ring.readyCount;++runs;if(real)++realRuns;
        RingAudit::active=nullptr;TargetAudit::elements=0;return got;
    }catch(const std::exception&e){throw std::runtime_error(std::to_string(p.M)+"x"+std::to_string(p.N)+" p="+std::to_string(p.pM)+","+std::to_string(p.pN)+" compact="+std::to_string(compact)+": "+e.what());}
}

template<class T,bool A,bool B>void pair(int batch,int M,int N,int K,int pm=1,int pn=1,int blocks=1){
    auto p=custom(batch,M,N,pm,pn,blocks);p.K=K;
    auto x=run<T,A,B>(p,false,0,false,true),y=run<T,A,B>(p,true,0,true,true);Mock::need(x==y,"old/new producer differs");
}
int main(){try{
#ifdef FAULT
    pair<half,true,false>(1,16,272,1056);return 7;
#endif
    pair<half,false,false>(1,16,272,1056);pair<half,false,true>(1,16,272,1056);
    pair<half,true,false>(1,16,272,1056);pair<half,true,true>(1,16,272,1056);
    pair<bfloat16_t,false,false>(1,16,272,1056);pair<bfloat16_t,false,true>(1,16,272,1056);
    pair<bfloat16_t,true,false>(1,16,272,1056);pair<bfloat16_t,true,true>(1,16,272,1056);
    pair<half,false,false>(1,144,272,1024,2,1,2);pair<bfloat16_t,true,true>(1,144,272,1024,2,1,2);
    pair<half,true,false>(1,16,528,1504,1,2,2);pair<bfloat16_t,false,true>(1,16,528,1504,1,2,2);
    pair<half,true,true>(3,16,272,1088,1,1,2);
    Mock::need(newA<oldA&&newB==oldB,"resident traffic not reduced");
    std::cout<<"{\"source_runs\":"<<runs<<",\"bitwise_equal_pairs\":"<<runs/2<<",\"old_A_bytes\":"<<oldA<<",\"new_A_bytes\":"<<newA
      <<",\"old_B_bytes\":"<<oldB<<",\"new_B_bytes\":"<<newB<<",\"ring_reads_elements\":"<<reads<<",\"ready_publications\":"<<credits<<",\"arena_peak_bytes\":[";
    for(int i=0;i<5;++i){if(i)std::cout<<",";std::cout<<OpStats::peak[i];}std::cout<<"]}\n";
}catch(const std::exception&e){std::cerr<<e.what()<<std::endl;return 1;}}

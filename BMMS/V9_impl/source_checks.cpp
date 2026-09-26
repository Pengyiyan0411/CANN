#define BMMS9_CPU_TEST 1
#include "cube_model.hpp"
#include "common_extracted.hpp"
#include "dense_extracted.hpp"
#if __has_include("splitk_extracted.hpp")
#include "splitk_extracted.hpp"
#endif
#include <iostream>
#include <iomanip>
#include <random>
#include <array>
#include <map>
#include <sstream>

int checks=0, repeats=0, strictMisses=0, combinedMisses=0, planChecks=0;
int denseRuns=0,splitRuns=0;
double maxError=0;
std::map<std::string,std::vector<uint32_t>> outputs;

template<class Fn>void workers(int count,Mock::Context&ctx,Fn fn,bool reverse,
                              Mock::Flags*flags=nullptr,int consumers=0){
    std::mutex mutex;std::string error;std::vector<std::thread> threads;
    for(int i=0;i<count;++i){int w=reverse?count-1-i:i;
        threads.emplace_back([&,w]{
            Mock::worker=w;Mock::logical=w;Mock::ctx=&ctx;Mock::flags=flags;
            Mock::localFlags={};
            if(flags){Mock::cube=w>=consumers;Mock::pairId=Mock::cube?w-consumers:w/2;Mock::subId=w%2;}
            try{
                fn(w);
                for(auto& ids:Mock::localFlags)for(int credit:ids)Mock::need(credit==0,"undrained local event");
            }catch(const std::exception&e){
                std::lock_guard l(mutex);if(error.empty())error=e.what();
                ctx.barrier.cancel();if(flags)flags->cancel();
            }
        });
    }
    for(auto&t:threads)t.join();
    if(!error.empty())throw std::runtime_error(error);
}

void assess(const std::string&key,const std::vector<float>&actual,const std::vector<double>&gold){
    std::vector<uint32_t>bits;
    for(size_t b=0;b<actual.size();++b){
        Mock::need(std::isfinite(actual[b]),"nonfinite result");
        double reference=float(gold[b]),err=std::abs(double(actual[b])-reference);
        double rel=reference==0?(err==0?0:INFINITY):err/std::abs(reference);
        maxError=std::max(maxError,err);
        if(!(err<1e-4&&rel<1e-4))++strictMisses;
        if(!(err<=1e-4+1e-4*std::abs(reference)))++combinedMisses;
        bits.push_back(std::bit_cast<uint32_t>(actual[b]));
    }
    if(outputs.count(key)){Mock::need(outputs[key]==bits,"nondeterministic CPU result");++repeats;}
    else outputs[key]=bits;
    ++checks;
}

template<class T,bool TA,bool TB>
void dense(int B,int M,int N,int K,int cores,int pattern,bool reverse){
    const std::string key="dense_"+std::to_string(sizeof(T))+"_"+(std::is_same_v<T,half>?"fp16":"bf16")+
        std::to_string(TA)+std::to_string(TB)+"_"+std::to_string(B)+"_"+std::to_string(M)+"_"+
        std::to_string(N)+"_"+std::to_string(K)+"_"+std::to_string(cores)+"_"+std::to_string(pattern);
    std::vector<T>a(int64_t(B)*M*K),b(int64_t(B)*K*N);
    auto ai=[&](int z,int m,int k){return int64_t(z)*M*K+(TA?int64_t(k)*M+m:int64_t(m)*K+k);};
    auto bi=[&](int z,int k,int n){return int64_t(z)*K*N+(TB?int64_t(n)*K+k:int64_t(k)*N+n);};
    std::mt19937 rng(901+B+M+N+K+pattern);std::uniform_int_distribution<int>rand(-4,4);
    for(int z=0;z<B;++z){
        for(int m=0;m<M;++m)for(int k=0;k<K;++k)a[ai(z,m,k)]=T((pattern?std::abs(rand(rng))+1:rand(rng))/32.f);
        for(int k=0;k<K;++k)for(int n=0;n<N;++n)b[bi(z,k,n)]=T((pattern?-std::abs(rand(rng))-1:rand(rng))/32.f);
    }
    std::vector<double>gold(B,0);
    for(int z=0;z<B;++z)for(int m=0;m<M;++m){
        double row=-INFINITY;
        for(int n=0;n<N;++n){double sum=0;for(int k=0;k<K;++k)sum+=double(float(a[ai(z,m,k)]))*float(b[bi(z,k,n)]);row=std::max(row,sum);}
        gold[z]+=row;
    }
    auto p=bmms9d::MakePlan(B,M,N,K,cores);
    std::vector<float>ring(bmms9d::RingBytes(p)/4,NAN),part(bmms9d::PartialBytes(p)/4,NAN),y(B,NAN);
    Mock::Context ctx(2*p.blocks);Mock::Flags flags(p.blocks);
    ctx.add(a.data(),a.size()*sizeof(T),true);ctx.add(b.data(),b.size()*sizeof(T),true);
    ctx.add(ring.data(),ring.size()*4,false);ctx.add(part.data(),part.size()*4,false);ctx.add(y.data(),y.size()*4,false);
    try{
        workers(3*p.blocks,ctx,[&](int w){
            AscendC::TPipe pipe;
            if(w>=2*p.blocks){
                Mock::logical=w-2*p.blocks;bmms9d::StagedProducer<T,TA,TB>op;
                op.Init(reinterpret_cast<GM_ADDR>(a.data()),reinterpret_cast<GM_ADDR>(b.data()),
                        reinterpret_cast<GM_ADDR>(ring.data()),p,&pipe);op.Process();
            }else{
                bmms83::SmallKConsumer op;
                op.Init(reinterpret_cast<GM_ADDR>(ring.data()),reinterpret_cast<GM_ADDR>(part.data()),
                        reinterpret_cast<GM_ADDR>(y.data()),p,&pipe);op.Process();
            }
        },reverse,&flags,2*p.blocks);
        flags.drained();assess(key,y,gold);++denseRuns;
    }catch(const std::exception&e){throw std::runtime_error(key+": "+e.what());}
}

#ifndef BMMS9_SKIP_SPLIT
template<class T>
void splitk(int B,int M,int N,int K,int cores,int pattern,bool reverse){
    Mock::need(bmms9s::Eligible(B,M,N,K,cores,false,true),"unsupported SplitK test input");
    const std::string key=std::string("split_")+(std::is_same_v<T,half>?"fp16":"bf16")+
        "_"+std::to_string(B)+"_"+std::to_string(M)+"_"+std::to_string(N)+"_"+
        std::to_string(K)+"_"+std::to_string(cores)+"_"+std::to_string(pattern);
    std::vector<T>a(int64_t(B)*M*K),b(int64_t(B)*N*K);
    std::mt19937 rng(1301+B+M+N+K+pattern);std::uniform_int_distribution<int>rand(-4,4);
    for(auto&v:a)v=T((pattern==1?std::abs(rand(rng))+1:rand(rng))/32.f);
    for(auto&v:b)v=T((pattern==1?-std::abs(rand(rng))-1:rand(rng))/32.f);
    if(pattern==2||pattern==3){
        for(auto&v:a)v=T(0);for(auto&v:b)v=T(0);
        if(pattern==2){
            Mock::need(M==2,"cancellation fixture requires 2 rows");
            for(int z=0;z<B;++z){
                a[(int64_t(z)*M)*K]=T(64);a[(int64_t(z)*M)*K+1]=T(0.015625f);
                a[(int64_t(z)*M+1)*K]=T(-64);
                for(int n=0;n<N;++n){b[(int64_t(z)*N+n)*K]=T(64);b[(int64_t(z)*N+n)*K+1]=T(0.0078125f);}
            }
        }
    }
    std::vector<double>gold(B,0);
    for(int z=0;z<B;++z)for(int m=0;m<M;++m){
        double row=-INFINITY;
        for(int n=0;n<N;++n){double sum=0;for(int k=0;k<K;++k)sum+=double(float(a[(int64_t(z)*M+m)*K+k]))*float(b[(int64_t(z)*N+n)*K+k]);row=std::max(row,sum);}
        gold[z]+=row;
    }
    auto p=bmms9s::MakePlan(B,M,N,K,cores);
    std::vector<float>part(bmms9s::WorkspaceBytes(p)/4,NAN),y(B,NAN);
    Mock::Context ctx(p.workers);
    ctx.add(a.data(),a.size()*sizeof(T),true);ctx.add(b.data(),b.size()*sizeof(T),true);
    ctx.add(part.data(),part.size()*4,false);ctx.add(y.data(),y.size()*4,false);
    try{
        workers(p.workers,ctx,[&](int){
            bmms9s::Device<T>(reinterpret_cast<GM_ADDR>(a.data()),reinterpret_cast<GM_ADDR>(b.data()),
                reinterpret_cast<GM_ADDR>(y.data()),reinterpret_cast<GM_ADDR>(part.data()),p);
        },reverse);
        assess(key,y,gold);++splitRuns;
        if(pattern==2)for(float v:y)Mock::need(v==0.0001220703125f,"lost compensated dot low part");
    }catch(const std::exception&e){throw std::runtime_error(key+": "+e.what());}
}
#endif

void planners(){
    for(int B:{1,2,3,20,64})for(int M:{16,48,64,80,256,8192})for(int N:{16,144,512,8192})
    for(int K:{256,288,320,352,512,1024,8192})for(int cores:{1,2,8,20,32,64}){
        if(int64_t(B)*M*K>(1LL<<26)||int64_t(B)*N*K>(1LL<<26))continue;
        auto p=bmms9d::MakePlan(B,M,N,K,cores);
        Mock::need(p.pN>=1&&p.pN<=p.nTiles&&p.blocks<=cores&&p.tasks>=p.blocks,"invalid dense launch plan");
        int coverage=0;
        for(int s=0;s<p.pM;++s){int lo=s*p.mTiles/p.pM,hi=(s+1)*p.mTiles/p.pM;Mock::need(hi>lo,"empty shard");coverage+=hi-lo;}
        Mock::need(coverage==p.mTiles,"dense partition coverage");++planChecks;
        int ncoverage=0;
        for(int s=0;s<p.pN;++s){int lo=s*p.nTiles/p.pN,hi=(s+1)*p.nTiles/p.pN;Mock::need(hi>lo,"empty N shard");ncoverage+=hi-lo;}
        Mock::need(ncoverage==p.nTiles,"dense N partition coverage");
    }
    for(auto dims:std::vector<std::array<int,3>>{{17,32,256},{16,17,256},{16,16,264},{16,16,128}})
        Mock::need(!bmms9d::Eligible(dims[0],dims[1],dims[2]),"dense accepted unsupported domain");
}

int main(){try{
    planners();
    for(int rev=0;rev<2;++rev)for(int pattern=0;pattern<2;++pattern){
        for(auto dims:std::vector<std::array<int,5>>{
            {1,16,16,256,2},{1,32,144,288,2},{1,80,16,320,2},
            {3,16,32,352,2},{1,16,528,256,1},{1,16,16,8192,1}}){
            auto [B,M,N,K,c]=dims;
            dense<half,false,false>(B,M,N,K,c,pattern,rev);
            dense<half,false,true>(B,M,N,K,c,pattern,rev);
            dense<half,true,false>(B,M,N,K,c,pattern,rev);
            dense<half,true,true>(B,M,N,K,c,pattern,rev);
            dense<bfloat16_t,false,false>(B,M,N,K,c,pattern,rev);
            dense<bfloat16_t,false,true>(B,M,N,K,c,pattern,rev);
            dense<bfloat16_t,true,false>(B,M,N,K,c,pattern,rev);
            dense<bfloat16_t,true,true>(B,M,N,K,c,pattern,rev);
        }
    }
    for(int rev=0;rev<2;++rev)for(int pattern=0;pattern<2;++pattern){
        dense<half,false,false>(1,80,528,320,6,pattern,rev);
        dense<bfloat16_t,true,true>(1,80,528,320,6,pattern,rev);
        dense<half,true,false>(3,16,1024,288,8,pattern,rev);
        dense<bfloat16_t,false,true>(1,16,1024,352,3,pattern,rev);
    }
#ifndef BMMS9_SKIP_SPLIT
    for(int rev=0;rev<2;++rev){
        for(int pattern:{0,1,3})for(auto dims:std::vector<std::array<int,5>>{
            {1,2,2,1024,20},{1,2,2,8192,20},{3,2,3,1032,8},
            {1,3,4,3080,20},{1,7,9,2040,20},{1,16,16,1024,20}}){
            auto[B,M,N,K,c]=dims;
            splitk<half>(B,M,N,K,c,pattern,rev);splitk<bfloat16_t>(B,M,N,K,c,pattern,rev);
        }
        splitk<half>(1,2,2,1024,20,2,rev);splitk<bfloat16_t>(1,2,2,1024,20,2,rev);
        splitk<half>(1,2,2,8192,20,2,rev);splitk<bfloat16_t>(1,2,2,8192,20,2,rev);
    }
#endif
    std::cout<<std::setprecision(12)<<"{\"device_test\":false,\"cann_compiled\":false,\"k_block\":"<<bmms9d::KB
        <<",\"source_runs\":"<<checks<<",\"repeat_pairs\":"<<repeats<<",\"plans_checked\":"<<planChecks
        <<",\"dense_runs\":"<<denseRuns<<",\"splitk_runs\":"<<splitRuns
        <<",\"strict_misses\":"<<strictMisses<<",\"combined_misses\":"<<combinedMisses<<",\"max_abs\":"<<maxError<<"}\n";
    return strictMisses?2:0;
}catch(const std::exception&e){std::cerr<<"STRUCTURAL_FAIL "<<e.what()<<"\n";return 1;}}

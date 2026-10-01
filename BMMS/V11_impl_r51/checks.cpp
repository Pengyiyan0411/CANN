#include "cpu_shim.hpp"
#include "baseline.hpp"
#include "r50.hpp"
#include "extracted.hpp"
#include <random>
#include <iostream>
#include <iomanip>
uint64_t runs=0,batches=0,tiny=0,resident=0,multiwave=0;double maxAbs=0;
template<class T,bool TA,bool TB>void run(int B,int M,int N,int K,int cores,int pattern){
    Mock::need(bmms51::Eligible(B,M,N,K),"fixture outside guard");
    auto p=bmms51::MakePlan(B,M,N,K,cores);
    std::mt19937 rng(51237+B*17+M*23+N*41+K*11+pattern);std::uniform_int_distribution<int> u(-8,8);
    std::uniform_real_distribution<float> f(-0.125f,0.125f);
    std::vector<T>a(B*M*K),b(B*N*K);
    for(auto& v:a)v=T(pattern==2?0:pattern==3?f(rng):pattern==1?(std::abs(u(rng))+1)/32.f:u(rng)/32.f);
    for(auto& v:b)v=T(pattern==2?0:pattern==3?f(rng):pattern==1?-(std::abs(u(rng))+1)/32.f:u(rng)/32.f);
    auto a0=a,b0=b;std::vector<double> ref(B,0);std::array<std::vector<float>,2> results{std::vector<float>(B,NAN),std::vector<float>(B,NAN)};
    for(int batch=0;batch<B;++batch)for(int m=0;m<M;++m){double row=-INFINITY;
        for(int n=0;n<N;++n){double dot=0;
            for(int k=0;k<K;++k)dot+=double(float(a[batch*M*K+(TA?k*M+m:m*K+k)]))*float(b[batch*N*K+(TB?n*K+k:k*N+n)]);
            row=std::max(row,dot);}ref[batch]+=row;}
    for(int mode=0;mode<2;++mode){
        Mock::Context ctx(p.workers);Mock::ctx=&ctx;
        ctx.add(a.data(),a.size()*sizeof(T),true);ctx.add(b.data(),b.size()*sizeof(T),true);ctx.add(results[mode].data(),B*4,false);
        for(int w=0;w<p.workers;++w){
            Mock::worker=w;Mock::logical=w;Mock::cube=false;Mock::pairId=w;Mock::subId=0;
            if(mode)bmms51::Device<T,TA,TB>((GM_ADDR)a.data(),(GM_ADDR)b.data(),(GM_ADDR)results[mode].data(),p);
            else if(p.tiny)bmmmaxsum_v43::TinyDevice<T,TA,TB>((GM_ADDR)a.data(),(GM_ADDR)b.data(),(GM_ADDR)results[mode].data(),B,M,N,K,p.workers);
            else bmms71::ResidentDevice<T,TA,TB>((GM_ADDR)a.data(),(GM_ADDR)b.data(),(GM_ADDR)results[mode].data(),B,M,N,K,p.kp,p.workers);
        }
        Mock::need(ctx.barrier.generation==0,"unexpected cross-core barrier");
        for(int i=0;i<B;++i)Mock::need(ctx.regions[2]->writer[i].load()==i%p.workers,"missing/wrong batch writer");
    }
    for(int i=0;i<B;++i){
        Mock::need(std::bit_cast<uint32_t>(results[0][i])==std::bit_cast<uint32_t>(results[1][i]),"baseline output mismatch");
        double err=std::abs(double(results[1][i])-float(ref[i]));maxAbs=std::max(maxAbs,err);
        Mock::need(std::isfinite(results[1][i])&&err<=1e-6+1e-5*std::abs(ref[i]),"reference mismatch");
    }
    Mock::need(std::memcmp(a0.data(),a.data(),a.size()*sizeof(T))==0&&std::memcmp(b0.data(),b.data(),b.size()*sizeof(T))==0,"input mutation");
    ++runs;batches+=B;if(p.tiny)++tiny;else ++resident;if(B>p.workers)++multiwave;
}
template<class T>void layouts(int b,int m,int n,int k,int c,int p){run<T,false,false>(b,m,n,k,c,p);run<T,false,true>(b,m,n,k,c,p);run<T,true,false>(b,m,n,k,c,p);run<T,true,true>(b,m,n,k,c,p);}
int main(){try{
#ifdef FAULT
    run<half,true,false>(9,3,5,72,2,0);return 9;
#endif
    for(int K=32;K<=128;K+=8)for(auto s:std::vector<std::array<int,2>>{{2,2},{2,8},{3,5},{4,4},{3,7},{5,11},{8,16},{15,13},{16,16}}){
        if(!bmms51::Eligible(2,s[0],s[1],K))continue;
        layouts<half>(3,s[0],s[1],K,20,0);layouts<bfloat16_t>(9,s[0],s[1],K,2,3);
    }
    for(auto s:std::vector<std::array<int,3>>{{2,7,40},{5,3,120},{7,15,96},{16,8,128},{16,16,64}})
      for(int B:{2,7,39,40,41,64})for(int c:{1,3,20,64}){
        layouts<half>(B,s[0],s[1],s[2],c,1);layouts<bfloat16_t>(B,s[0],s[1],s[2],c,2);
    }
    std::cout<<std::setprecision(12)<<"{\"shape_layout_pattern_pairs\":"<<runs<<",\"actual_source_runs\":"<<2*runs
        <<",\"batch_outputs_compared\":"<<batches<<",\"tiny_pairs\":"<<tiny<<",\"resident_pairs\":"<<resident
        <<",\"multiwave_pairs\":"<<multiwave<<",\"bitwise_equal_pairs\":"<<runs<<",\"max_abs_vs_fp64_reference\":"<<maxAbs
        <<",\"model_UB_peak_bytes\":"<<OpStats::peak[0]<<"}\n";
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}

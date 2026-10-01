#include "cpu_shim.hpp"
#include "baseline.hpp"
#include "r50.hpp"
#include "extracted.hpp"
#include <random>
#include <iostream>
#include <iomanip>
template<class T,bool A,bool B>void candidate(GM_ADDR a,GM_ADDR b,GM_ADDR y,bmms50::Plan p){switch(p.K){
case 32:bmms1203::Device<T,A,B,32>(a,b,y,p);return;
case 40:bmms1203::Device<T,A,B,40>(a,b,y,p);return;
case 48:bmms1203::Device<T,A,B,48>(a,b,y,p);return;
case 56:bmms1203::Device<T,A,B,56>(a,b,y,p);return;
case 64:bmms1203::Device<T,A,B,64>(a,b,y,p);return;
case 72:bmms1203::Device<T,A,B,72>(a,b,y,p);return;
case 80:bmms1203::Device<T,A,B,80>(a,b,y,p);return;
case 88:bmms1203::Device<T,A,B,88>(a,b,y,p);return;
case 96:bmms1203::Device<T,A,B,96>(a,b,y,p);return;
case 104:bmms1203::Device<T,A,B,104>(a,b,y,p);return;
case 112:bmms1203::Device<T,A,B,112>(a,b,y,p);return;
case 120:bmms1203::Device<T,A,B,120>(a,b,y,p);return;
case 128:bmms1203::Device<T,A,B,128>(a,b,y,p);return;
}throw std::runtime_error("invalid K");}
int runs=0,tiny=0,resident=0;double maxAbs=0;
template<class T,bool TA,bool TB>void run(int M,int N,int K,int pattern){
    Mock::need(bmms50::Eligible(1,M,N,K),"fixture outside guard");
    std::mt19937 rng(50237+M*23+N*41+K*11+pattern);std::uniform_int_distribution<int> u(-8,8);
    std::uniform_real_distribution<float> f(-0.125f,0.125f);
    std::vector<T>a(M*K),b(N*K);
    for(auto& v:a)v=T(pattern==2?0:pattern==3?f(rng):pattern==1?(std::abs(u(rng))+1)/32.f:u(rng)/32.f);
    for(auto& v:b)v=T(pattern==2?0:pattern==3?f(rng):pattern==1?-(std::abs(u(rng))+1)/32.f:u(rng)/32.f);
    auto a0=a,b0=b;double ref=0;
    for(int m=0;m<M;++m){double row=-INFINITY;
        for(int n=0;n<N;++n){double dot=0;
            for(int k=0;k<K;++k)dot+=double(float(a[TA?k*M+m:m*K+k]))*float(b[TB?n*K+k:k*N+n]);
            row=std::max(row,dot);}ref+=row;}
    float results[2]={NAN,NAN};
    auto p=bmms50::MakePlan(M,N,K);
    for(int mode=0;mode<2;++mode){
        Mock::Context ctx(1);Mock::ctx=&ctx;Mock::worker=0;Mock::logical=0;Mock::cube=false;Mock::pairId=0;Mock::subId=0;
        ctx.add(a.data(),a.size()*sizeof(T),true);ctx.add(b.data(),b.size()*sizeof(T),true);ctx.add(&results[mode],4,false);
        if(mode)candidate<T,TA,TB>((GM_ADDR)a.data(),(GM_ADDR)b.data(),(GM_ADDR)&results[mode],p);
        else bmms50::Device<T,TA,TB>((GM_ADDR)a.data(),(GM_ADDR)b.data(),(GM_ADDR)&results[mode],p);
        Mock::need(ctx.barrier.generation==0,"unexpected cross-core barrier");
    }
    Mock::need(std::bit_cast<uint32_t>(results[0])==std::bit_cast<uint32_t>(results[1]),"baseline output mismatch");
    double err=std::abs(double(results[1])-float(ref));maxAbs=std::max(maxAbs,err);
    Mock::need(std::isfinite(results[1])&&err<1e-4&&(ref==0?err==0:err/std::abs(ref)<1e-4),"reference mismatch");
    Mock::need(std::memcmp(a0.data(),a.data(),a.size()*sizeof(T))==0&&std::memcmp(b0.data(),b.data(),b.size()*sizeof(T))==0,"input mutation");
    ++runs;if(p.tiny)++tiny;else ++resident;
}
template<class T>void layouts(int m,int n,int k,int p){run<T,false,false>(m,n,k,p);run<T,false,true>(m,n,k,p);run<T,true,false>(m,n,k,p);run<T,true,true>(m,n,k,p);}
int main(){try{
#ifdef FAULT
    run<half,true,false>(3,5,64,0);return 9;
#endif
    for(int K=32;K<=128;K+=8)for(auto s:std::vector<std::array<int,2>>{{2,2},{2,8},{3,5},{4,4},{3,7},{5,11},{8,16},{15,13},{16,16}}){
        if(!bmms50::Eligible(1,s[0],s[1],K))continue;
        layouts<half>(s[0],s[1],K,0);layouts<bfloat16_t>(s[0],s[1],K,3);
    }
    for(auto s:std::vector<std::array<int,3>>{{2,7,40},{5,3,120},{7,15,96},{16,8,128},{16,16,64}}){
        layouts<half>(s[0],s[1],s[2],1);layouts<bfloat16_t>(s[0],s[1],s[2],2);
    }
    std::cout<<std::setprecision(12)<<"{\"shape_layout_pattern_pairs\":"<<runs<<",\"actual_source_runs\":"<<2*runs
        <<",\"tiny_pairs\":"<<tiny<<",\"resident_pairs\":"<<resident<<",\"bitwise_equal_pairs\":"<<runs<<",\"max_abs_vs_fp64_reference\":"<<maxAbs
        <<",\"model_UB_peak_bytes\":"<<OpStats::peak[0]<<"}\n";
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}

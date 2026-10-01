#include "cpu_shim.hpp"
#include "baseline.hpp"
#include "extracted.hpp"
#include <random>
#include <iostream>
#include <iomanip>
template<class T>void candidate(GM_ADDR a,GM_ADDR b,GM_ADDR y,int k){
#define C(K) case K:bmms52::Device<T,K>(a,b,y);return;
    switch(k){C(32) C(40) C(48) C(56) C(64) C(72) C(80) C(88) C(96) C(104) C(112) C(120) C(128)}
#undef C
    throw std::runtime_error("missing static K");
}
uint64_t runs=0;double maxAbs=0;
template<class T>void run(int K,int pattern,int seed){
    std::mt19937 rng(seed);std::uniform_int_distribution<int> u(-8,8);std::uniform_real_distribution<float> f(-0.125f,0.125f);
    std::vector<T>a(K),b(K);
    for(int k=0;k<K;++k){
        a[k]=T(pattern==0?u(rng)/32.f:pattern==1?f(rng):pattern==2?float(std::abs(u(rng))+1)/32.f:pattern==3?0.f:0.25f);
        b[k]=T(pattern==0?u(rng)/32.f:pattern==1?f(rng):pattern==2?-float(std::abs(u(rng))+1)/32.f:pattern==3?0.f:((k&1)?-0.125f:0.125f));
    }
    auto a0=a,b0=b;double ref=0;for(int k=0;k<K;++k)ref+=double(float(a[k]))*float(b[k]);
    float out[2]={NAN,NAN};
    for(int mode=0;mode<2;++mode){
        Mock::Context ctx(1);Mock::ctx=&ctx;Mock::worker=Mock::logical=Mock::pairId=Mock::subId=0;Mock::cube=false;
        ctx.add(a.data(),K*sizeof(T),true);ctx.add(b.data(),K*sizeof(T),true);ctx.add(out+mode,4,false);
        if(mode)candidate<T>((GM_ADDR)a.data(),(GM_ADDR)b.data(),(GM_ADDR)(out+mode),K);
        else bmmmaxsum_v43::DotDevice<T>((GM_ADDR)a.data(),(GM_ADDR)b.data(),(GM_ADDR)(out+mode),1,K,1);
        Mock::need(ctx.regions[2]->writer[0].load()==0,"missing scalar output");
        Mock::need(ctx.barrier.generation==0,"unexpected cross-core barrier");
    }
    Mock::need(std::bit_cast<uint32_t>(out[0])==std::bit_cast<uint32_t>(out[1]),"baseline output mismatch");
    double err=std::abs(double(out[1])-float(ref));maxAbs=std::max(maxAbs,err);
    Mock::need(std::isfinite(out[1])&&err<=1e-6+1e-5*std::abs(ref),"reference mismatch");
    Mock::need(std::memcmp(a0.data(),a.data(),K*sizeof(T))==0&&std::memcmp(b0.data(),b.data(),K*sizeof(T))==0,"input mutation");++runs;
}
int main(){try{
#ifdef FAULT
    run<half>(64,0,52237);return 9;
#endif
    for(int K=32;K<=128;K+=8)for(int p=0;p<5;++p)for(int seed:{7,52,52237,20260928}){
        run<half>(K,p,seed);run<bfloat16_t>(K,p,seed);
    }
    std::cout<<std::setprecision(12)<<"{\"K_dtype_pattern_seed_pairs\":"<<runs<<",\"actual_source_runs\":"<<2*runs
        <<",\"bitwise_equal_pairs\":"<<runs<<",\"max_abs_vs_fp64_reference\":"<<maxAbs
        <<",\"model_UB_peak_bytes\":"<<OpStats::peak[0]<<"}\n";
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}

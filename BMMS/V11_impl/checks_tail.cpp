template<class T>void layouts(std::array<int,5> d,int pat,bool rev){
    auto[B,M,N,K,c]=d;
    dense<T,false,false>(B,M,N,K,c,pat,rev);dense<T,false,true>(B,M,N,K,c,pat,rev);
    dense<T,true,false>(B,M,N,K,c,pat,rev);dense<T,true,true>(B,M,N,K,c,pat,rev);
}
void planners(){
    for(int B:{1,2,3,20,64})for(int M:{16,128,144,272,8192})for(int N:{16,256,272,528,8192})
    for(int K:{256,288,320,352,512,544,8192})for(int cores:{1,2,3,8,20,64}){
        if(int64_t(B)*M*K>(1LL<<26)||int64_t(B)*N*K>(1LL<<26))continue;
        auto p=bmms11::MakePlan(B,M,N,K,cores);
        Mock::need(p.mTiles==(M+127)/128&&p.nTiles==(N+255)/256,"plan not macro aligned");
        Mock::need(p.blocks<=cores&&p.blocks<=p.tasks&&p.pM<=p.mTiles&&p.pN<=p.nTiles,"invalid launch plan");
        int mc=0,nc=0;
        for(int s=0;s<p.pM;++s){int lo=s*p.mTiles/p.pM,hi=(s+1)*p.mTiles/p.pM;Mock::need(hi>lo,"empty M shard");mc+=hi-lo;}
        for(int s=0;s<p.pN;++s){int lo=s*p.nTiles/p.pN,hi=(s+1)*p.nTiles/p.pN;Mock::need(hi>lo,"empty N shard");nc+=hi-lo;}
        Mock::need(mc==p.mTiles&&nc==p.nTiles,"shard coverage");
        bool expect=M>=128&&N>=256&&int64_t(B)*p.mTiles*p.nTiles>=cores;
        Mock::need(bmms11::Eligible(B,M,N,K,cores)==expect,"guard disagrees with domain/occupancy");
        if(expect)Mock::need(p.blocks==cores,"eligible plan loses AIC occupancy");++planChecks;
    }
    for(auto v:std::vector<std::array<int,5>>{{1,127,256,256,1},{1,128,255,256,1},
        {1,144,272,264,1},{1,128,256,128,1},{1,128,256,256,2},
        {65,128,256,256,1},{1,128,256,256,0},{1,128,256,256,65},{64,8192,8192,8192,64}})
        Mock::need(!bmms11::Eligible(v[0],v[1],v[2],v[3],v[4]),"unsupported guard accepted");
}
int main(){try{
#ifdef CHECK_R01
    planners();
    for(int rev=0;rev<2;++rev){
        for(auto d:std::vector<std::array<int,5>>{
            {1,128,256,256,1},{1,144,272,288,2},{1,80,144,320,1},
            {1,16,16,352,1},{1,16,16,8192,1},{3,16,32,544,2}}){
            layouts<half>(d,0,rev);layouts<bfloat16_t>(d,0,rev);
        }
        for(auto d:std::vector<std::array<int,5>>{
            {1,272,528,352,3},{1,128,256,512,1},{1,128,256,544,1},
            {3,144,272,256,4},{1,128,1024,288,3},{1,8192,16,256,2}}){
            dense<half,false,true>(d[0],d[1],d[2],d[3],d[4],0,rev);
            dense<bfloat16_t,true,false>(d[0],d[1],d[2],d[3],d[4],0,rev);
        }
        for(int pat:{1,2}){
            layouts<half>({1,144,272,288,2},pat,rev);
            layouts<bfloat16_t>({1,144,272,288,2},pat,rev);
        }
    }
    dense<half,false,false>(1,128,256,256,1,4,false);
    dense<bfloat16_t,false,false>(1,128,256,256,1,4,false);
    dense<bfloat16_t,false,false>(1,128,256,256,1,5,false);
    Mock::need(knownLimits==3,"known limitations missing");
#endif
    Traffic::reset();dense<half,false,false>(1,128,256,256,1,0,false);
    std::cout<<std::setprecision(12)<<"{\"source_runs\":"<<checks<<",\"repeat_pairs\":"<<repeats
        <<",\"plan_checks\":"<<planChecks<<",\"strict_misses\":"<<strictMisses<<",\"combined_misses\":"<<combinedMisses
        <<",\"max_abs\":"<<maxError<<",\"known_precision_limitations\":"<<knownLimits
        <<",\"pipe_m_barriers\":"<<Mock::pipeMBarriers.load()
        <<",\"traffic_fixture\":{\"gm_bytes\":"<<Traffic::gmInputBytes.load()<<",\"gm_calls\":"<<Traffic::gmCopies.load()
        <<",\"l0_bytes\":"<<Traffic::l0Bytes.load()<<",\"l0_calls\":"<<Traffic::l0Copies.load()<<",\"mmads\":"<<Traffic::mmads.load()
        <<",\"publishes\":"<<Traffic::publishes.load()<<",\"c_write_bytes\":"<<Traffic::cWriteBytes.load()<<"},\"output_bits\":{";
    bool first=true;for(auto&[key,bits]:outputs){if(!first)std::cout<<",";first=false;std::cout<<"\""<<key<<"\":[";
        for(size_t i=0;i<bits.size();++i){if(i)std::cout<<",";std::cout<<bits[i];}std::cout<<"]";}
    std::cout<<"},\"cann_compiled\":false,\"npu_tested\":false,\"full_domain_precision_accepted\":false}\n";
    return strictMisses?2:0;
}catch(const std::exception&e){std::cerr<<"STRUCTURAL_FAIL "<<e.what()<<"\n";return 1;}}

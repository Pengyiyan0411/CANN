struct Metrics {uint64_t runs=0,zero=0,read=0,write=0;};

template<class P,class F>void runPack(const P& p,F fn,int schedulingSeed,Metrics& total){
    std::vector<half> a(int64_t(p.realM)*p.realK),b(int64_t(p.realK)*p.realN);
    // Each operand contains every possible 16-bit value, including FP16/BF16
    // negative zero, infinities and NaN payloads. No numerical conversion.
    for(size_t i=0;i<a.size();++i)a[i].bits=uint16_t(i*40503u+1u);
    for(size_t i=0;i<b.size();++i)b[i].bits=uint16_t(i*32771u+11u);
    auto aBefore=a,bBefore=b;
    constexpr int guard=16;
    std::vector<half> aw(int64_t(p.cube.M)*p.cube.K+2*guard),bw(int64_t(p.cube.K)*p.cube.N+2*guard);
    for(auto& x:aw)x.bits=0xf17e;
    for(auto& x:bw)x.bits=0xf17e;
    auto ap=aw.data()+guard,bp=bw.data()+guard;
    auto oldZero=Model::zeroWords,oldRead=Model::dmaReadWords,oldWrite=Model::storeWords;
    const int workers=2*p.cube.blocks;
    std::vector<int> order(workers);std::iota(order.begin(),order.end(),0);
    if(schedulingSeed){std::mt19937 rng(schedulingSeed);std::shuffle(order.begin(),order.end(),rng);}
    else std::reverse(order.begin(),order.end());
    for(int worker:order){
        Model::Graph graph;Model::graph=&graph;Model::worker=worker;Model::resetWorker();
        AscendC::TPipe pipe;AscendC::TBuf<AscendC::TPosition::VECCALC> buf;
        pipe.InitBuffer(buf,2*32768*2);
        fn(reinterpret_cast<GM_ADDR>(a.data()),reinterpret_cast<GM_ADDR>(b.data()),
           reinterpret_cast<GM_ADDR>(ap),reinterpret_cast<GM_ADDR>(bp),p,&pipe,buf);
        need(Model::packedAll&&Model::waitedAll&&Model::releasedCube,"pack handoff missing");
        for(auto e:Model::events)need(!e.allocated,"event leaked");
        graph.execute(schedulingSeed?uint32_t(schedulingSeed+worker*37):0);
    }
    // Independent matrix oracle: padded[r,c] = source[r,c] in original domain,
    // and exactly +0 everywhere else. This does not use the pack job formula.
    auto compare=[](const auto& desc,const auto& src,const half* dst){
        for(int r=0;r<desc.dstRows;++r)for(int c=0;c<desc.dstCols;++c){
            uint16_t expected=(r<desc.srcRows&&c<desc.srcCols)?src[int64_t(r)*desc.srcCols+c].bits:0;
            need(dst[int64_t(r)*desc.dstCols+c].bits==expected,"padded bits differ from 2-D oracle");
        }
    };
    compare(p.a,a,ap);compare(p.b,b,bp);
    for(size_t i=0;i<a.size();++i)need(a[i].bits==aBefore[i].bits,"A input changed");
    for(size_t i=0;i<b.size();++i)need(b[i].bits==bBefore[i].bits,"B input changed");
    for(int i=0;i<guard;++i){
        need(aw[i].bits==0xf17e&&aw[aw.size()-1-i].bits==0xf17e,"A output canary changed");
        need(bw[i].bits==0xf17e&&bw[bw.size()-1-i].bits==0xf17e,"B output canary changed");
    }
    ++total.runs;total.zero+=Model::zeroWords-oldZero;
    total.read+=Model::dmaReadWords-oldRead;total.write+=Model::storeWords-oldWrite;
}

int main(){try{
    uint64_t descriptors=0,jobs=0,gapJobs=0,tailJobs=0,pureTailJobs=0;
    uint64_t oldWords=0,newWords=0;int maxRepeat=0,maxStride=0;
    for(int size=1024;size<2048;++size)for(int k=1032;k<1280;k+=8)for(int trans=0;trans<2;++trans){
        int ps=(size+15)/16*16,pk=(k+31)/32*32;
        auto d=trans?candidate::MakePackDesc(k,size,pk,ps):candidate::MakePackDesc(size,k,ps,pk);
        ++descriptors;int readRows=0,writtenRows=0;
        const int pitch=(d.srcCols+15)/16*16,gap=d.dstCols-pitch;
        need(gap==0||gap==16,"unexpected DMA row gap");
        need(pitch%16==0&&pitch>=d.srcCols&&pitch-d.srcCols<=15,"DMA right padding");
        for(int j=0;j<d.jobs;++j){
            int row0=j*d.rowsPerJob,rows=std::min(d.rowsPerJob,d.dstRows-row0);
            int live=std::max(0,std::min(rows,d.srcRows-row0));++jobs;
            need(rows>0&&rows*d.dstCols<=32768,"slot capacity");
            need(live<=rows&&live<=32&&d.dstCols/16<=128,"repeat bounds");
            if(gap&&live){++gapJobs;maxRepeat=std::max(maxRepeat,live);maxStride=std::max(maxStride,d.dstCols/16);}
            if(live<rows){++tailJobs;if(!live)++pureTailJobs;}
            // Partition each destination row into payload, explicit DMA pad,
            // extra vector-zero gap, or a complete padded row. No holes.
            need(live*(d.srcCols+(pitch-d.srcCols)+gap)+(rows-live)*d.dstCols==rows*d.dstCols,"row coverage");
            need((row0+live<=d.srcRows)||!live,"source row overread");
            oldWords+=uint64_t(rows)*d.dstCols;
            newWords+=uint64_t(live)*gap+uint64_t(rows-live)*d.dstCols;
            writtenRows+=rows;readRows+=live;
        }
        need(writtenRows==d.dstRows&&readRows==d.srcRows,"operand row coverage");
    }
    const int fixtures[][4]={
        {1024,1025,1032,1},{1025,1024,1040,2},
        {1039,1041,1048,8},{1040,1039,1056,20},
        {1279,1281,1208,32},{1985,2015,1264,64},
        {2047,2047,1272,20},{2047,1025,1248,64}
    };
    Metrics oldM,newM;
    for(auto& f:fixtures)for(int ta=0;ta<2;++ta)for(int tb=0;tb<2;++tb)for(int schedule:{0,193}){
        auto p=control::MakePlan(f[0],f[1],f[2],f[3],ta,tb);
        need(control::ValidPlan(p,f[3]),"baseline plan invalid");
        runPack(p,control::PackInputs,schedule,oldM);
        auto q=candidate::MakePlan(f[0],f[1],f[2],f[3],ta,tb);
        need(candidate::ValidPlan(q,f[3]),"candidate plan invalid");
        runPack(q,candidate::PackInputs,schedule,newM);
    }
    need(oldM.runs==newM.runs&&oldM.read==newM.read&&oldM.write==newM.write,"packing work changed unexpectedly");
    need(newM.zero<oldM.zero,"no zero work was removed");
    int rejected=0;
    for(int fault:{1,2}){
        Model::fault=fault;bool failed=false;
        try{auto p=candidate::MakePlan(1025,1041,1032,2,false,false);Metrics dummy;runPack(p,candidate::PackInputs,317,dummy);}
        catch(const std::exception&){failed=true;}
        need(failed,"oracle missed omitted padding writes");++rejected;
    }
    Model::fault=0;
    std::cout<<"{\"geometry_descriptors\":"<<descriptors<<",\"geometry_jobs\":"<<jobs
      <<",\"gap_jobs\":"<<gapJobs<<",\"tail_jobs\":"<<tailJobs<<",\"pure_padding_jobs\":"<<pureTailJobs
      <<",\"max_gap_repeat\":"<<maxRepeat<<",\"max_gap_repeat_stride_blocks\":"<<maxStride
      <<",\"geometry_R43_zero_words\":"<<oldWords<<",\"geometry_R45_zero_words\":"<<newWords
      <<",\"R43_actual_source_pack_runs\":"<<oldM.runs<<",\"R45_actual_source_pack_runs\":"<<newM.runs
      <<",\"fixture_R43_zero_words\":"<<oldM.zero<<",\"fixture_R45_zero_words\":"<<newM.zero
      <<",\"fixture_GM_read_words_each_version\":"<<oldM.read<<",\"fixture_GM_write_words_each_version\":"<<oldM.write
      <<",\"missing_padding_faults_rejected\":"<<rejected<<"}\n";
    return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}

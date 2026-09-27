// A full-tile ownership contract, NOT a model of hardware UnitFlag timing.
// Executed alongside actual producer C++ to reject unpaired/partial transactions.
namespace UnitContract {
struct Live {const Mock::Buffer* buffer;size_t offset,bytes;int m,n;};
// Two producer L0C slots, plus spare entries for adversarial contract checks.
// Trivial TLS avoids a MinGW/UCRT TLS-destructor issue in this Windows harness.
inline thread_local std::array<Live,4> live{};
inline thread_local bool rowMajor=false;
inline bool overlap(const Live& x,const Mock::Buffer* b,size_t off,size_t size){
    return x.bytes&&x.buffer==b&&off<x.offset+x.bytes&&x.offset<off+size;
}
inline void beforeMmad(const Mock::Buffer* b,size_t off,int m,int n,int flag,bool init){
    const size_t size=size_t(m)*n*4;
    for(auto& x:live)Mock::need(!overlap(x,b,off,size),"UnitFlag L0C overwrite before full consumption");
    if(!flag)return;
    Mock::need(flag==3&&init,"UnitFlag candidate requires one complete initialized MMAD");
    Mock::need(rowMajor,"UnitFlag NZ2ND producer direction not set");
    auto free=std::find_if(live.begin(),live.end(),[](const Live& x){return x.bytes==0;});
    Mock::need(free!=live.end(),"UnitFlag contract capacity exceeded");
    *free={b,off,size,m,n};++UnitStats::mmads;
}
inline void beforeFix(const Mock::Buffer* b,size_t off,int m,int n,int stride,int count,int flag){
    auto it=std::find_if(live.begin(),live.end(),[&](const Live& x){return x.bytes&&x.buffer==b&&x.offset==off;});
    if(!flag){Mock::need(it==live.end(),"UnitFlag MMAD without matching FIX flag");return;}
    Mock::need(flag==3&&it!=live.end(),"UnitFlag FIX without matching MMAD flag");
    Mock::need(m==it->m&&n==it->n&&stride==m&&count==1,"UnitFlag incomplete full-tile consumption");
    *it={};++UnitStats::fixes;
}
inline void reset(){live={};rowMajor=false;}
inline void drained(){
    for(auto& x:live)Mock::need(x.bytes==0,"UnitFlag L0C state leaked");
    Mock::need(!rowMajor,"MMAD direction not restored after drain");
}
}

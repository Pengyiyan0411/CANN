// Source-CPU stage ownership audit, not a model of hardware caches or pipeline timing.
namespace ReductionAudit {
struct State {
    uintptr_t base;size_t originalElements,scratchElements;int workers,B,M,pN;
    bool scratchEnabled;
    std::vector<uint64_t> originalReads,scratchReads,scratchWrites;
    std::unique_ptr<std::atomic<int>[]> written;
    State(float* ptr,int b,int m,int pn,int count,bool enabled):base((uintptr_t)ptr),
        originalElements(size_t(b)*m*pn),scratchElements(size_t(b)*m),workers(count),B(b),M(m),pN(pn),
        scratchEnabled(enabled),originalReads(count),scratchReads(count),scratchWrites(count),
        written(new std::atomic<int>[scratchElements]){
        for(size_t i=0;i<scratchElements;++i)written[i]=0;
    }
    void read(uintptr_t addr){
        if(addr<base||addr>=base+(originalElements+(scratchEnabled?scratchElements:0))*4)return;
        Mock::need(!Mock::cube&&Mock::worker<workers,"unexpected partial reader");
        size_t index=(addr-base)/4;
        if(index<originalElements){++originalReads[Mock::worker];return;}
        Mock::need(Mock::ctx->barrier.generation>=2,"merged rows read before completion barrier");
        Mock::need(written[index-originalElements].load()==1,"merged row not written exactly once");
        ++scratchReads[Mock::worker];
    }
    void write(uintptr_t addr){
        if(!scratchEnabled||addr<base+originalElements*4||addr>=base+(originalElements+scratchElements)*4)return;
        size_t index=(addr-base)/4-originalElements;
        const int chunks=(M+127)/128,expected=int((index/M)*chunks+(index%M)/128)%workers;
        Mock::need(Mock::worker==expected,"wrong merged-row owner");
        Mock::need(written[index].fetch_add(1)==0,"duplicate merged-row write");++scratchWrites[Mock::worker];
    }
    void check(bool parallel){
        uint64_t nr=0,nw=0;
        for(int w=0;w<workers;++w){nr+=scratchReads[w];nw+=scratchWrites[w];}
        Mock::need(nr==(parallel?scratchElements:0)&&nw==nr,"wrong merged scratch coverage");
    }
    uint64_t peakReads()const{
        uint64_t peak=0;for(int w=0;w<workers;++w)peak=std::max(peak,originalReads[w]+scratchReads[w]);return peak;
    }
};
inline State* active=nullptr;
inline void read(uintptr_t addr){if(active)active->read(addr);}
inline void write(uintptr_t addr){if(active)active->write(addr);}
}

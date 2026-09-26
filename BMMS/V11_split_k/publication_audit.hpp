// CPU protocol audit for immutable split-K partials, separate from the old ring audit.
namespace SplitAudit {
struct State {
    uintptr_t base;int B,M,N,S,blocks,mt,nt;std::vector<int> reads,published,waited;
    std::mutex mutex;uint64_t writes=0,totalReads=0;
    State(void* ptr,int b,int m,int n,int s,int groups):base((uintptr_t)ptr),B(b),M(m),N(n),S(s),blocks(groups),mt((m+63)/64),nt((n+127)/128),
        reads(groups*64*128,0),published(groups,0),waited(2*groups,0){}
    void write(void* ptr,int mr,int nr){
        std::lock_guard lock(mutex);int group=((uintptr_t)ptr-base)/(64*128*4);
        Mock::need(Mock::cube&&group==Mock::pairId&&(uintptr_t)ptr==base+size_t(group)*64*128*4,"split producer owns wrong partial");
        int tile=group/S,n=tile%nt,m=(tile/nt)%mt;
        Mock::need(mr==std::min(64,M-m*64)&&nr==std::min(128,N-n*128),"split write geometry mismatch");
        writes+=uint64_t(mr)*nr;
    }
    void ready(int id){std::lock_guard lock(mutex);
        Mock::need(Mock::cube&&id==4&&++published[Mock::pairId]==1,"split publication repeated or wrong flag");}
    void wait(int id){std::lock_guard lock(mutex);
        Mock::need(!Mock::cube&&id==4&&++waited[Mock::worker]==1,"split wait repeated or wrong flag");}
    void read(void* ptr,int rows,int bytes,int stride){
        uintptr_t a=(uintptr_t)ptr;
        if(a<base||a>=base+reads.size()*4)return;
        std::lock_guard lock(mutex);
        Mock::need(!Mock::cube&&Mock::ctx->barrier.generation==1,"split partial read before publication barrier");
        for(int r=0;r<rows;++r)for(int col=0;col<bytes/4;++col){
            size_t i=(a-base)/4+r*(bytes+stride)/4+col;
            Mock::need(i<reads.size(),"split DMA exceeds workspace");
            int group=i/(64*128),tile=group/S,cell=i%(64*128),n=tile%nt,m=(tile/nt)%mt,b=tile/(mt*nt);
            Mock::need(b==Mock::worker&&published[group]==1,"wrong batch owner or unpublished split read");
            Mock::need(cell/128<std::min(64,M-m*64)&&cell%128<std::min(128,N-n*128),"split DMA reads GM padding");
            Mock::need(++reads[i]==1,"split partial read more than once");++totalReads;
        }
    }
    void check(){
        Mock::need(writes==uint64_t(B)*M*N*S&&totalReads==writes,"split partial coverage mismatch");
        for(int n:published)Mock::need(n==1,"unpublished Cube task");
        for(int n:waited)Mock::need(n==1,"missing per-group AIV acknowledgement");
    }
};
inline State* active=nullptr;
inline void write(void* p,int m,int n){if(active)active->write(p,m,n);}
inline void ready(int id){if(active)active->ready(id);}
inline void wait(int id){if(active)active->wait(id);}
inline void read(void* p,int r,int bytes,int stride){if(active)active->read(p,r,bytes,stride);}
}

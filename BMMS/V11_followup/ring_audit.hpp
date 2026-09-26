// CPU-only ownership audit. Does not emulate hardware pipelines/cache visibility.
namespace RingAudit {
struct Slot {
    bool published=false;uint64_t writes=0,reads[2]={0,0};bool freed[2]={false,false};
};
struct State {
    uintptr_t base;size_t bytes,slotBytes;
    std::vector<Slot> slots;std::mutex mutex;
    uint64_t readyCount=0,freeCount=0,readElements=0,writeElements=0;
    State(void* p,size_t groups,size_t slotElements):base((uintptr_t)p),
        bytes(groups*2*slotElements*4),slotBytes(slotElements*4),slots(groups*2){}
    int index(void* ptr){
        uintptr_t p=(uintptr_t)ptr;
        if(p<base||p>=base+bytes)return -1;
        return int((p-base)/slotBytes);
    }
    void write(void* ptr,uint64_t elements){
        std::lock_guard lock(mutex);int i=index(ptr);
        Mock::need(i>=0&&i/2==Mock::pairId&&Mock::cube,"Fixpipe writes outside owned ring group");
        auto& s=slots[i];Mock::need(!s.published,"Fixpipe overwrites a published ring slot");
        s.writes+=elements;writeElements+=elements;
    }
    void read(void* ptr,uint64_t elements){
        std::lock_guard lock(mutex);int i=index(ptr);if(i<0)return;
        Mock::need(!Mock::cube&&i/2==Mock::pairId,"AIV reads another group's ring");
        auto& s=slots[i];Mock::need(s.published&&!s.freed[Mock::subId],"ring read without a live publication");
        s.reads[Mock::subId]+=elements;readElements+=elements;
        Mock::need(s.reads[Mock::subId]<=s.writes/2,"consumer reads more than its published half");
    }
    void ready(int slot){
        std::lock_guard lock(mutex);Mock::need(Mock::cube&&slot>=0&&slot<2,"bad ready sender");
        auto& s=slots[Mock::pairId*2+slot];
        Mock::need(!s.published&&s.writes>0&&s.writes%2==0,"invalid ring publication");
        s.published=true;++readyCount;
    }
    void free(int slot){
        std::lock_guard lock(mutex);Mock::need(!Mock::cube&&slot>=0&&slot<2,"bad free sender");
        auto& s=slots[Mock::pairId*2+slot];
        Mock::need(s.published&&!s.freed[Mock::subId],"duplicate/unpublished release");
        Mock::need(s.reads[Mock::subId]==s.writes/2,"ring freed before all published data was read");
        s.freed[Mock::subId]=true;++freeCount;
        if(s.freed[0]&&s.freed[1])s=Slot{};
    }
    void drained(){
        for(auto& s:slots)Mock::need(!s.published&&!s.writes&&!s.reads[0]&&!s.reads[1],"ring ownership not drained");
        Mock::need(readElements==writeElements&&freeCount==2*readyCount,"ring byte/credit conservation mismatch");
    }
};
inline State* active=nullptr;
inline void write(void* p,uint64_t n){if(active)active->write(p,n);}
inline void read(void* p,uint64_t n){if(active)active->read(p,n);}
inline void signal(int id){if(active){if(Mock::cube)active->ready(id-4);else active->free(id-6);}}
inline uint64_t lastReady=0,lastFree=0,lastReads=0,lastWrites=0;
}

// Semantic test adapter only. NOT an Ascend simulator and NOT part of submission.
// CPU operations + deferred Matmul requests + CPU barrier: checks indexing, bounds, initialization,
// row pitches, ownership and numerical semantics. Does not model device pipes/KFC.
#pragma once

#include <algorithm>
#include <array>
#include <atomic>
#include <barrier>
#include <bit>
#include <cmath>
#include <condition_variable>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <functional>
#include <limits>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>
#define __aicore__
#define __gm__
using GM_ADDR = unsigned char*;
using event_t = int;
constexpr int PIPE_V=0, PIPE_ALL=1, PIPE_MTE2=2, PIPE_MTE3=3, PIPE_FIX=4, PIPE_M=5;
struct half {
    uint16_t bits{};
    half()=default;
    half(int x):half(float(x)){}
    half(float x) { _Float16 t=(_Float16)x; std::memcpy(&bits,&t,2); }
    operator float() const { _Float16 x; std::memcpy(&x,&bits,2); return float(x); }
};
struct bfloat16_t {
    uint16_t bits{};
    bfloat16_t()=default;
    bfloat16_t(int x):bfloat16_t(float(x)){}
    bfloat16_t(float x) { uint32_t u=std::bit_cast<uint32_t>(x); u+=0x7fff+((u>>16)&1); bits=u>>16; }
    operator float() const {return std::bit_cast<float>(uint32_t(bits)<<16);}
};
static_assert(sizeof(half)==2 && sizeof(bfloat16_t)==2);
struct TCubeTiling {int baseM=0,baseN=0,baseK=0,singleCoreM=0,singleCoreN=0,singleCoreK=0,usedCoreNum=1,stepM=1,stepN=1,iterateOrder=1;};
enum class CubeFormat {ND};
namespace Mock {
inline thread_local int worker=0;
inline thread_local int logical=0;
inline thread_local bool cube=false;
inline thread_local int pairId=0,subId=0;
inline thread_local bool deferred=true;
inline thread_local bool smallMmadPending=false;
inline std::atomic<uint64_t> pipeMBarriers{0};
inline std::atomic<int64_t> requests{0}, asyncRequests{0}, waits{0};
struct Barrier {
    int expected,arrived=0,generation=0; bool broken=false;
    std::mutex m;std::condition_variable cv;
    explicit Barrier(int n):expected(n){}
    void cancel(){std::lock_guard<std::mutex> l(m);broken=true;cv.notify_all();}
    void wait(){std::unique_lock<std::mutex> l(m);int g=generation;
        if(broken)throw std::runtime_error("cancelled barrier");
        if(++arrived==expected){arrived=0;++generation;cv.notify_all();}
        else cv.wait(l,[&]{return broken||g!=generation;});
        if(broken)throw std::runtime_error("cancelled barrier");}
};
struct Region {
    uintptr_t start; size_t bytes; bool input;
    std::unique_ptr<std::atomic<int>[]> writer;
    Region(void* p,size_t n,bool in):start((uintptr_t)p),bytes(n),input(in),writer(new std::atomic<int>[(n+3)/4]) {
        for(size_t i=0;i<(n+3)/4;++i)writer[i].store(in?-2:-1);
    }
};
struct Context {
    std::vector<std::unique_ptr<Region>> regions;
    Barrier barrier;
    explicit Context(int n):barrier(n){}
    void add(void* p,size_t n,bool input){regions.emplace_back(new Region(p,n,input));}
    Region* locate(uintptr_t addr,size_t bytes){for(auto& r:regions) {
        if(addr>=r->start && addr-r->start<=r->bytes && bytes<=r->bytes-(addr-r->start))return r.get(); }
        throw std::runtime_error("GM address outside registered allocation");}
};
inline thread_local Context* ctx=nullptr;
inline thread_local std::array<std::array<int,8>,32> localFlags{};
inline void need(bool v,const char* msg){if(!v)throw std::runtime_error(msg);}
struct Buffer {int arena=-1;std::vector<uint8_t> bytes,init;
    explicit Buffer(size_t n):bytes(n,0xa5),init(n,0){}
};
}
// CPU-only ownership audit. Does not emulate hardware pipelines/cache visibility.
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

namespace RingAudit {
struct Slot {
    bool published=false;uint64_t writes=0,reads[2]={0,0};bool freed[2]={false,false};unsigned tileMask[2]={0,0};
};
struct State {
    uintptr_t base;size_t bytes,slotBytes;int wholeTileElements=0;bool batchOwner=false;
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
        
        if(batchOwner){Mock::need(Mock::subId==(Mock::pairId&1)&&s.reads[Mock::subId]<=s.writes,"wrong batch owner or duplicate read");}
        else if(wholeTileElements){
            const int tile=(uintptr_t(ptr)-base-size_t(i)*slotBytes)/(64*128*4);
            Mock::need(elements==wholeTileElements&&tile%2==Mock::subId,"wrong whole-tile consumer owner");
            Mock::need(!(s.tileMask[Mock::subId]&(1u<<tile)),"whole tile read twice");
            s.tileMask[Mock::subId]|=1u<<tile;
        }else Mock::need(s.reads[Mock::subId]<=s.writes/2,"consumer reads more than its published half");
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
        
        const uint64_t expected=batchOwner?(Mock::subId==(Mock::pairId&1)?s.writes:0):wholeTileElements?
            ((s.writes/wholeTileElements+1-Mock::subId)/2)*wholeTileElements:s.writes/2;
        Mock::need(s.reads[Mock::subId]==expected,"ring freed before all published data was read");
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

// Logical bytes copied by actual source API calls, not cache/HBM counters or timing.
namespace TrafficAB {
inline uintptr_t aBegin=0,aEnd=0,bBegin=0,bEnd=0;
inline std::atomic<uint64_t> aBytes{0},bBytes{0},aCopies{0},bCopies{0},l1Peak{0};
inline void chargeL1(uint64_t n){auto old=l1Peak.load();while(old<n&&!l1Peak.compare_exchange_weak(old,n)){};}
inline void begin(uintptr_t a,size_t as,uintptr_t b,size_t bs){
    aBegin=a;aEnd=a+as;bBegin=b;bEnd=b+bs;aBytes=0;bBytes=0;aCopies=0;bCopies=0;l1Peak=0;
}
inline void copied(uintptr_t src,uint64_t bytes){
    if(src>=aBegin&&src<aEnd){aBytes+=bytes;++aCopies;}
    else if(src>=bBegin&&src<bEnd){bBytes+=bytes;++bCopies;}
    else throw std::runtime_error("ND2NZ source is not a registered operand");
}
}

namespace OpStats {
inline std::atomic<uint64_t> duplicateElements{0},reduceCalls{0},reduceRows{0},manualVToMte2{0};
inline std::array<std::atomic<uint64_t>,5> peak{};
inline void charge(int arena,uint64_t n){auto old=peak[arena].load();while(old<n&&!peak[arena].compare_exchange_weak(old,n)){};}
inline void reset(){duplicateElements=0;reduceCalls=0;reduceRows=0;manualVToMte2=0;}
}

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


namespace TargetAudit {
inline uintptr_t partial=0;inline size_t elements=0;
inline std::atomic<uint64_t> dmaCalls{0},reads{0},writes{0};
inline std::vector<unsigned> visits;
inline void begin(float* p,size_t n){partial=(uintptr_t)p;elements=n;dmaCalls=0;reads=0;writes=0;visits.assign(n,0);}
inline bool inside(uintptr_t p){return p>=partial&&p<partial+elements*4;}
inline void dma(uintptr_t p){if(inside(p))++dmaCalls;}
inline void read(uintptr_t p){if(inside(p)){
    Mock::need(Mock::ctx->barrier.generation==1,"partial read before original barrier");
    ++reads;++visits[(p-partial)/4];}}
inline void write(uintptr_t p){if(inside(p))++writes;}
}
namespace AscendC {
enum class TPosition {GM,VECIN,VECOUT,VECCALC,A1,B1,A2,B2,CO1};
enum class HardEvent {MTE2_V,V_MTE2,MTE2_S,MTE3_MTE2,V_MTE3,MTE3_V,V_S,S_V,MTE2_MTE1,MTE1_MTE2,MTE1_M,M_MTE1,M_FIX,FIX_M,S_MTE3,MTE3_S};
enum class RoundMode {CAST_NONE};
enum class ReduceOrder {ORDER_ONLY_VALUE};
struct BinaryRepeatParams {uint8_t dstBlkStride,src0BlkStride,src1BlkStride,dstRepStride,src0RepStride,src1RepStride;};
struct DataCopyExtParams {uint16_t blockCount;uint32_t blockLen,srcStride,dstStride,rsv;};
template<class T>struct DataCopyPadExtParams {bool isPad;uint8_t leftPadding,rightPadding;T paddingValue;};
template<class T>struct LocalTensor {
    std::shared_ptr<Mock::Buffer> b;size_t offset=0;
    T GetValue(size_t i)const {size_t o=offset+i*sizeof(T);Mock::need(b&&o<=b->bytes.size()&&sizeof(T)<=b->bytes.size()-o,"UB read out of bounds");
        for(size_t j=0;j<sizeof(T);++j)Mock::need(b->init[o+j],"UB uninitialized read");
        T v;std::memcpy(&v,b->bytes.data()+o,sizeof(T));return v;}
    void SetValue(size_t i,T v)const {size_t o=offset+i*sizeof(T);Mock::need(b&&o<=b->bytes.size()&&sizeof(T)<=b->bytes.size()-o,"UB write out of bounds");
        std::memcpy(b->bytes.data()+o,&v,sizeof(T));std::fill_n(b->init.data()+o,sizeof(T),1);}
    LocalTensor operator[](size_t i)const {auto t=*this;t.offset+=i*sizeof(T);Mock::need(t.offset<=b->bytes.size(),"UB view out of bounds");return t;}
    template<class U>LocalTensor<U> ReinterpretCast()const {return {b,offset};}
};
template<class T>struct GlobalTensor {
    T* p=nullptr;size_t n=0;
    void SetGlobalBuffer(T* x,int64_t c){Mock::need(c>=0,"negative GM size");p=x;n=c;
        if(c)Mock::ctx->locate((uintptr_t)x,c*sizeof(T));}
    GlobalTensor operator[](size_t i)const {Mock::need(i<=n,"GM view out of bounds");return {p+i,n-i};}
    T GetValue(size_t i)const {Mock::need(i<n,"GM read out of view bounds");
        auto r=Mock::ctx->locate((uintptr_t)(p+i),sizeof(T));
        ReductionAudit::read((uintptr_t)(p+i));TargetAudit::read((uintptr_t)(p+i));
        if(!r->input){size_t j=((uintptr_t)(p+i)-r->start)/4;Mock::need(r->writer[j].load()>=0,"uninitialized GM read");}
        return p[i];}
    void SetValue(size_t i,T v)const {Mock::need(i<n,"GM write out of view bounds");
        auto r=Mock::ctx->locate((uintptr_t)(p+i),sizeof(T));Mock::need(!r->input,"input modified");
        size_t j=((uintptr_t)(p+i)-r->start)/4;
        ReductionAudit::write((uintptr_t)(p+i));TargetAudit::write((uintptr_t)(p+i));
        int prev=r->writer[j].load();
        if(prev==-1){int unset=-1;r->writer[j].compare_exchange_strong(unset,Mock::worker);prev=r->writer[j].load();}
        Mock::need(prev==Mock::worker,"GM location written by multiple workers");p[i]=v;
    }
};
template<TPosition P,int D>struct TQue {
    std::shared_ptr<Mock::Buffer> storage;bool allocated=false,enqueued=false;
    template<class T>LocalTensor<T> AllocTensor(){Mock::need(!allocated,"queue double allocation");allocated=true;std::fill(storage->init.begin(),storage->init.end(),0);return {storage,0};}
    template<class T>void EnQue(LocalTensor<T>){Mock::need(allocated&&!enqueued,"queue EnQue mismatch");enqueued=true;}
    template<class T>LocalTensor<T> DeQue(){Mock::need(allocated&&enqueued,"queue DeQue mismatch");enqueued=false;return {storage,0};}
    template<class T>void FreeTensor(LocalTensor<T>){Mock::need(allocated&&!enqueued,"queue Free mismatch");allocated=false;}
};
template<TPosition P>struct TBuf {std::shared_ptr<Mock::Buffer> storage;
    template<class T>LocalTensor<T> Get(){return {storage,0};}};
struct TPipe {
    std::array<size_t,5> used{};
    std::array<std::array<bool,8>,32> eventUsed{};
    template<TPosition P> void charge(size_t n) {
        constexpr int arena=(P==TPosition::A1||P==TPosition::B1)?1:
                            P==TPosition::A2?2:P==TPosition::B2?3:P==TPosition::CO1?4:0;
        constexpr size_t caps[5]={192*1024,512*1024,64*1024,64*1024,128*1024};
        used[arena]+=n;if constexpr(arena==1)TrafficAB::chargeL1(used[arena]);OpStats::charge(arena,used[arena]);Mock::need(used[arena]<=caps[arena],"per-arena resource budget exceeded");
    }
    template<TPosition P,int D>void InitBuffer(TQue<P,D>& q,int depth,size_t n){
        Mock::need(depth==1,"CPU queue adapter currently supports depth one");
        q.storage=std::make_shared<Mock::Buffer>(n);charge<P>(depth*n);
    }
    template<TPosition P>void InitBuffer(TBuf<P>& b,size_t n){b.storage=std::make_shared<Mock::Buffer>(n);b.storage->arena=P==TPosition::A2?2:P==TPosition::B2?3:-1;charge<P>(n);}
    int FetchEventID(HardEvent){return 0;}
    template<HardEvent E>int AllocEventID(){
        auto& ids=eventUsed[int(E)];for(int i=0;i<8;++i)if(!ids[i]){ids[i]=true;return i;}
        throw std::runtime_error("event allocator exhausted");
    }
    template<HardEvent E>void ReleaseEventID(int i){
        Mock::need(i>=0&&i<8&&eventUsed[int(E)][i],"invalid event release");eventUsed[int(E)][i]=false;
    }
};
inline int GetBlockIdx(){return Mock::logical;}
template<HardEvent E>void SetFlag(int id){if constexpr(E==HardEvent::V_MTE2)++OpStats::manualVToMte2;Mock::need(id>=0&&id<8,"event id out of range");auto& n=Mock::localFlags[int(E)][id];Mock::need(n==0,"local event credit overwritten");++n;}
template<HardEvent E>void WaitFlag(int id){if constexpr(E==HardEvent::M_FIX)Mock::smallMmadPending=false;auto& n=Mock::localFlags[int(E)][id];Mock::need(n==1,"local event wait has no credit");--n;}
template<int P>void PipeBarrier(){if constexpr(P==PIPE_M){++Mock::pipeMBarriers;Mock::smallMmadPending=false;}}
template<bool only>void SyncAll(){static_assert(only);Mock::ctx->barrier.wait();}
template<class T>void Duplicate(LocalTensor<T> d,T x,int n){OpStats::duplicateElements+=n;for(int i=0;i<n;++i)d.SetValue(i,x);}
template<class T,class U>void Cast(LocalTensor<T>d,LocalTensor<U>s,RoundMode,int n){for(int i=0;i<n;++i)d.SetValue(i,T(float(s.GetValue(i))));}
template<class T>void Mul(LocalTensor<T>d,LocalTensor<T>a,LocalTensor<T>b,int n){for(int i=0;i<n;++i)d.SetValue(i,a.GetValue(i)*b.GetValue(i));}
template<class T>void Muls(LocalTensor<T>d,LocalTensor<T>a,T k,int n){for(int i=0;i<n;++i)d.SetValue(i,a.GetValue(i)*k);}
template<class T>void CreateVecIndex(LocalTensor<T>d,T v,int n){for(int i=0;i<n;++i)d.SetValue(i,v+i);}
template<class T>void Gather(LocalTensor<T>d,LocalTensor<T>s,LocalTensor<uint32_t> idx,uint32_t base,int n){for(int i=0;i<n;++i){auto j=idx.GetValue(i)+base;Mock::need(j%sizeof(T)==0,"unaligned gather index");d.SetValue(i,s.GetValue(j/sizeof(T)));}}
template<class T>void aligned(LocalTensor<T> x){Mock::need(x.offset%32==0,"UB intrinsic address not 32-byte aligned");}
inline float sumtree(std::vector<float> v) {
    Mock::need(!v.empty(),"empty sum");
    while(v.size()>1) {size_t w=0;for(size_t i=0;i<v.size();i+=2)v[w++]=i+1<v.size()?v[i]+v[i+1]:v[i];v.resize(w);}return v[0];
}
inline void Mul(LocalTensor<float>d,LocalTensor<float>a,LocalTensor<float>b,int mask,int repeats,BinaryRepeatParams p){
    aligned(d);aligned(a);aligned(b);Mock::need(mask>=1&&mask<=64&&repeats>=1&&repeats<=255,"bad Mul mask/repeats");
    for(int r=0;r<repeats;++r)for(int i=0;i<mask;++i){auto ix=[&](int bs,int rs){return r*rs*8+(i/8)*bs*8+i%8;};
        d.SetValue(ix(p.dstBlkStride,p.dstRepStride),a.GetValue(ix(p.src0BlkStride,p.src0RepStride))*b.GetValue(ix(p.src1BlkStride,p.src1RepStride)));}}
inline void Add(LocalTensor<float>d,LocalTensor<float>a,LocalTensor<float>b,int mask,int repeats,BinaryRepeatParams p){
    aligned(d);aligned(a);aligned(b);Mock::need(mask>=1&&mask<=64&&repeats>=1&&repeats<=255,"bad Add mask/repeats");
    for(int r=0;r<repeats;++r)for(int i=0;i<mask;++i){auto ix=[&](int bs,int rs){return r*rs*8+(i/8)*bs*8+i%8;};
        d.SetValue(ix(p.dstBlkStride,p.dstRepStride),a.GetValue(ix(p.src0BlkStride,p.src0RepStride))+b.GetValue(ix(p.src1BlkStride,p.src1RepStride)));}}
inline void WholeReduceSum(LocalTensor<float>d,LocalTensor<float>s,int mask,int repeats,int ds,int bs,int rs){
    aligned(d);aligned(s);Mock::need(mask>=1&&mask<=64&&repeats>=1&&repeats<=255,"bad WholeReduceSum");
    for(int r=0;r<repeats;++r){std::vector<float> v;for(int i=0;i<mask;++i)v.push_back(s.GetValue(r*rs*8+(i/8)*bs*8+i%8));d.SetValue(r*ds,sumtree(v));}}
inline void BlockReduceSum(LocalTensor<float>d,LocalTensor<float>s,int repeats,int mask,int ds,int bs,int rs){
    aligned(d);aligned(s);Mock::need(repeats>=1&&repeats<=255&&mask==64,"bad BlockReduceSum");
    for(int r=0;r<repeats;++r)for(int g=0;g<8;++g){std::vector<float>v;for(int i=0;i<8;++i)v.push_back(s.GetValue(r*rs*8+g*bs*8+i));d.SetValue(r*ds*8+g,sumtree(v));}}
inline void BlockReduceMax(LocalTensor<float>d,LocalTensor<float>s,int repeats,int mask,int ds,int bs,int rs){
    aligned(d);aligned(s);Mock::need(repeats>=1&&repeats<=255&&mask==64,"bad BlockReduceMax");
    for(int r=0;r<repeats;++r)for(int g=0;g<8;++g){float v=-INFINITY;for(int i=0;i<8;++i)v=std::max(v,s.GetValue(r*rs*8+g*bs*8+i));d.SetValue(r*ds*8+g,v);}}
inline float max_checked(float a,float b){Mock::need(!std::isnan(a)&&!std::isnan(b),"NaN max operand");return a>b?a:b;}
inline void Max(LocalTensor<float>d,LocalTensor<float>a,LocalTensor<float>b,int n){for(int i=0;i<n;++i)d.SetValue(i,max_checked(a.GetValue(i),b.GetValue(i)));}
inline void Max(LocalTensor<float>d,LocalTensor<float>a,LocalTensor<float>b,int mask,int repeats,BinaryRepeatParams p){
    Mock::need(mask>=1&&mask<=64&&repeats<=255,"bad vector mask/repeats");
    for(int r=0;r<repeats;++r)for(int i=0;i<mask;++i){auto ix=[&](int bs,int rs){return r*rs*8+(i/8)*bs*8+i%8;};
        d.SetValue(ix(p.dstBlkStride,p.dstRepStride),max_checked(a.GetValue(ix(p.src0BlkStride,p.src0RepStride)),b.GetValue(ix(p.src1BlkStride,p.src1RepStride))));}}
inline void WholeReduceMax(LocalTensor<float>d,LocalTensor<float>s,int mask,int repeats,int ds,int bs,int rs,ReduceOrder){++OpStats::reduceCalls;OpStats::reduceRows+=repeats;
    aligned(d);aligned(s);Mock::need(mask>0&&mask<=64&&repeats>=1&&repeats<=255,"bad WholeReduceMax parameters");
    for(int r=0;r<repeats;++r){float x=-INFINITY;for(int i=0;i<mask;++i)x=max_checked(x,s.GetValue(r*rs*8+(i/8)*bs*8+i%8));d.SetValue(r*ds,x);}}
inline void ReduceSum(LocalTensor<float>d,LocalTensor<float>s,LocalTensor<float>,int n){
    std::vector<float> v(n);for(int i=0;i<n;++i)v[i]=s.GetValue(i);
    while(v.size()>1){size_t w=0;for(size_t i=0;i<v.size();i+=2)v[w++]=i+1<v.size()?v[i]+v[i+1]:v[i];v.resize(w);}d.SetValue(0,v.at(0));}
template<class T>void DataCopy(LocalTensor<T>d,GlobalTensor<T>s,int n){TargetAudit::dma((uintptr_t)s.p);Mock::need(n*sizeof(T)%32==0,"unaligned DataCopy length");for(int i=0;i<n;++i)d.SetValue(i,s.GetValue(i));}
template<class T>void DataCopy(GlobalTensor<T>d,LocalTensor<T>s,int n){Mock::need(n*sizeof(T)%32==0,"unaligned DataCopy length");for(int i=0;i<n;++i)d.SetValue(i,s.GetValue(i));}
template<class T>void DataCopyPad(LocalTensor<T>d,GlobalTensor<T>s,DataCopyExtParams cp,DataCopyPadExtParams<T> pad){TargetAudit::dma((uintptr_t)s.p);
    SplitAudit::read(s.p,cp.blockCount,cp.blockLen,cp.srcStride);
    RingAudit::read(s.p,uint64_t(cp.blockCount)*cp.blockLen/sizeof(T));
    Mock::need(cp.blockLen%sizeof(T)==0&&cp.srcStride%sizeof(T)==0,"bad DataCopyPad GM pitch");
    int len=cp.blockLen/sizeof(T),left=pad.isPad?pad.leftPadding:0,right=pad.isPad?pad.rightPadding:0;
    int ubstep=((len+left+right)*sizeof(T)+31)/32*32/sizeof(T)+cp.dstStride*32/sizeof(T);
    int gmstep=(cp.blockLen+cp.srcStride)/sizeof(T);
    for(int r=0;r<cp.blockCount;++r){for(int i=0;i<left;++i)d.SetValue(r*ubstep+i,pad.paddingValue);
        for(int i=0;i<len;++i)d.SetValue(r*ubstep+left+i,s.GetValue(r*gmstep+i));
        for(int i=0;i<right;++i)d.SetValue(r*ubstep+left+len+i,pad.paddingValue);}}
template<class T>void DataCopyPad(GlobalTensor<T>d,LocalTensor<T>s,DataCopyExtParams cp){
    Mock::need(cp.blockLen%sizeof(T)==0,"bad DataCopyPad write");int len=cp.blockLen/sizeof(T);
    int ubstep=(cp.blockLen+31)/32*32/sizeof(T)+cp.srcStride*32/sizeof(T),gmstep=(cp.blockLen+cp.dstStride)/sizeof(T);
    for(int r=0;r<cp.blockCount;++r)for(int i=0;i<len;++i)d.SetValue(r*gmstep+i,s.GetValue(r*ubstep+i));}
}

namespace Mock {
struct Pair {
    int ready[2][2]{};
    int free[2]{};
    unsigned ack[2]{};
    unsigned pairAck=0;
    int done[2]{};
};
struct Flags {
    std::vector<Pair> pairs;
    std::mutex m;std::condition_variable cv;
    bool cancelled=false;
    uint64_t published=0,released=0,acquired=0,consumed=0;
    explicit Flags(int n):pairs(n){}
    void cancel(){std::lock_guard l(m);cancelled=true;cv.notify_all();}
    template<int MODE,int PIPE> void set(int id) {
        std::lock_guard l(m);need(!cancelled,"cancelled flags");
        auto& p=pairs.at(pairId);
        if constexpr(MODE==2) {
            if(cube) {
                need(PIPE==PIPE_FIX&&id>=0&&id<2,"bad producer publication");
                for(int j=0;j<2;++j){need(p.ready[j][id]==0,"unconsumed ready token");++p.ready[j][id];}
                ++published;
            }else{
                need(PIPE==PIPE_MTE2&&id>=2&&id<4,"bad consumer release");
                int slot=id-2;need(!(p.ack[slot]&(1U<<subId)),"duplicate AIV acknowledgement");
                p.ack[slot]|=1U<<subId;
                if(p.ack[slot]==3){p.ack[slot]=0;++p.free[slot];need(p.free[slot]==1,"stale free token");++released;}
            }
        }else{
            static_assert(MODE==1);need(!cube&&id==8&&PIPE==PIPE_MTE3,"bad pair barrier");
            need(!(p.pairAck&(1U<<subId)),"duplicate pair arrival");p.pairAck|=1U<<subId;
            if(p.pairAck==3){p.pairAck=0;++p.done[0];++p.done[1];}
        }
        cv.notify_all();
    }
    template<int MODE> void wait(int id) {
        std::unique_lock l(m);auto& p=pairs.at(pairId);int* token=nullptr;
        if constexpr(MODE==2) {
            if(cube){need(id>=2&&id<4,"bad producer wait");token=&p.free[id-2];}
            else{need(id>=0&&id<2,"bad consumer wait");token=&p.ready[subId][id];}
        } else {static_assert(MODE==1);need(!cube&&id==8,"bad pair wait");token=&p.done[subId];}
        bool ok=cv.wait_for(l,std::chrono::seconds(10),[&]{return cancelled||*token>0;});
        need(ok,"timeout: unmatched flag / deadlock");need(!cancelled,"cancelled flags");
        --*token;
        if constexpr(MODE==2){if(cube)++acquired;else ++consumed;}
    }
    void drained(){for(auto& p:pairs){for(int s=0;s<2;++s)need(!p.free[s]&&!p.ack[s]&&!p.ready[0][s]&&!p.ready[1][s],"residual ring flags");need(!p.done[0]&&!p.done[1]&&!p.pairAck,"residual pair flags");}
        if(SplitAudit::active)need(published==pairs.size()&&released==0&&acquired==0&&consumed==published*2,"immutable publication token conservation failure");else need(published==released&&released==acquired&&consumed==published*2,"token conservation failure");}
};
inline thread_local Flags* flags=nullptr;
}
namespace AscendC {
template<int MODE,int PIPE>void CrossCoreSetFlag(uint16_t id){if constexpr(MODE==2){if(Mock::cube)SplitAudit::ready(id);RingAudit::signal(id);}Mock::flags->set<MODE,PIPE>((MODE==2 && id>=4 && id<=7)?id-4:id);if(((Mock::worker+id)&3)==0)std::this_thread::yield();}
template<int MODE>void CrossCoreWaitFlag(uint16_t id){Mock::flags->wait<MODE>((MODE==2 && id>=4 && id<=7)?id-4:id);if constexpr(MODE==2){if(!Mock::cube)SplitAudit::wait(id);}}
}

// Independent *normative* Matmul grouping model. This is not an NPU emulator.
// FlatFastStream() is verified against this grouped output, not against the
// consumer's flat-index assumption. Safe IterateAll writes an explicit stride.
namespace matmul {
template<AscendC::TPosition P,CubeFormat F,class T,bool TR=false>
struct MatmulType{using type=T;static constexpr bool tr=TR;static constexpr auto pos=P;};
template<class A,class B,class C>struct Matmul{
    AscendC::GlobalTensor<typename A::type> a;
    AscendC::GlobalTensor<typename B::type> b;
    TCubeTiling td;int M=0,N=0,K=0,pitch=0,rm=0,rn=0,rk=0;
    bool complete=false,pending=false;size_t next=0,current=0;
    std::vector<std::pair<int,int>> coords;
    void Init(const TCubeTiling* x,AscendC::TPipe*){td=*x;}
    void SetOrgShape(int m,int n,int ka,int kb,int kc=0){
        M=m;N=n;K=ka;pitch=kc?kc:n;Mock::need(ka==kb,"K mismatch");}
    void SetTensorA(decltype(a) x,bool t){a=x;Mock::need(t==A::tr,"A layout mismatch");}
    void SetTensorB(decltype(b) x,bool t){b=x;Mock::need(t==B::tr,"B layout mismatch");}
    void SetSingleShape(int m,int n,int k){
        rm=m;rn=n;rk=k;complete=false;next=0;coords.clear();pending=false;
        Mock::need(k==K&&m>0&&n>0,"bad single shape");
        if constexpr(C::pos==AscendC::TPosition::VECIN){
            int mt=(m+td.baseM-1)/td.baseM,nt=(n+td.baseN-1)/td.baseN;
            Mock::need(td.stepM>0&&td.stepN>0,"invalid grouping");
            if(td.iterateOrder==1){
                for(int mb=0;mb<mt;mb+=td.stepM)
                    for(int nn=0;nn<nt;++nn)
                        for(int mm=mb;mm<std::min(mt,mb+td.stepM);++mm)coords.emplace_back(mm,nn);
            }else{
                for(int nb=0;nb<nt;nb+=td.stepN)
                    for(int mm=0;mm<mt;++mm)
                        for(int nn=nb;nn<std::min(nt,nb+td.stepN);++nn)coords.emplace_back(mm,nn);
            }
        }
    }
    void CheckInputs(){
        a.GetValue(A::tr?(K-1)*M+rm-1:(rm-1)*K+K-1);
        b.GetValue(B::tr?(rn-1)*K+K-1:(K-1)*N+rn-1);
    }
    float Dot(int m,int n){float sum=0;
        for(int k=0;k<K;++k)sum=std::fma(float(a.p[A::tr?k*M+m:m*K+k]),float(b.p[B::tr?n*K+k:k*N+n]),sum);
        return sum;}
    template<bool SYNC>void IterateAll(AscendC::GlobalTensor<float> c,int atom,bool seq){
        Mock::need(SYNC&&!atom&&!seq,"unexpected IterateAll mode");CheckInputs();
        Mock::need(pitch>=rn,"bad C stride");
        for(int m=rm-1;m>=0;--m)for(int n=rn-1;n>=0;--n)c.SetValue(m*pitch+n,Dot(m,n));
        complete=true;
    }
    template<bool SYNC>bool Iterate(){
        Mock::need(SYNC&&!pending,"GetTensorC missing");
        if(next==coords.size()){complete=true;return false;}
        CheckInputs();current=next++;pending=true;return true;
    }
    template<bool SYNC>void GetTensorC(AscendC::LocalTensor<float> c,int atom,bool seq){
        Mock::need(SYNC&&!atom&&seq&&pending,"GetTensorC mode/state mismatch");
        auto [mt,nt]=coords[current];int m0=mt*td.baseM,n0=nt*td.baseN;
        int rows=std::min(td.baseM,rm-m0),cols=std::min(td.baseN,rn-n0);
        for(int m=0;m<rows;++m)for(int n=0;n<cols;++n)c.SetValue(m*cols+n,Dot(m0+m,n0+n));
        pending=false;
    }
    void End(){Mock::need(complete&&!pending,"premature Matmul End");}
};
}

namespace AscendC {
template<class T>void Add(LocalTensor<T>d,LocalTensor<T>a,LocalTensor<T>b,int n){for(int i=0;i<n;++i)d.SetValue(i,a.GetValue(i)+b.GetValue(i));}
template<class T>void Sub(LocalTensor<T>d,LocalTensor<T>a,LocalTensor<T>b,int n){for(int i=0;i<n;++i)d.SetValue(i,a.GetValue(i)-b.GetValue(i));}
template<class T>void ShiftRight(LocalTensor<T>d,LocalTensor<T>a,T b,int n){for(int i=0;i<n;++i)d.SetValue(i,a.GetValue(i)>>b);}
}

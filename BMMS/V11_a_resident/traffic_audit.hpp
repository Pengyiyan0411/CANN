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

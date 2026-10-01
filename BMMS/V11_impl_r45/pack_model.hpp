// CPU-only model for the extracted PackInputs function. This is not CANN.
#include <algorithm>
#include <array>
#include <cstdint>
#include <functional>
#include <iostream>
#include <limits>
#include <map>
#include <numeric>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>
#define __aicore__
#define __gm__
using GM_ADDR = uint8_t*;
constexpr int PIPE_MTE3=2;
inline void need(bool v,const char* msg){if(!v)throw std::runtime_error(msg);}
struct half {
    uint16_t bits=0;
    half()=default;
    explicit half(float v){need(v==0.0f,"model only constructs zero");}
};
static_assert(sizeof(half)==2);

namespace Model {
struct Node {std::vector<int> deps;std::function<void()> op;};
struct Graph {
    std::vector<Node> nodes;
    int tail[3]={-1,-1,-1};
    int push(int pipe,std::function<void()> op={},int extra=-1){
        Node n;
        if(tail[pipe]>=0)n.deps.push_back(tail[pipe]);
        if(extra>=0&&extra!=tail[pipe])n.deps.push_back(extra);
        n.op=std::move(op);nodes.push_back(std::move(n));
        return tail[pipe]=int(nodes.size())-1;
    }
    void execute(uint32_t seed){
        std::vector<int> left(nodes.size()),ready;
        std::vector<std::vector<int>> children(nodes.size());
        for(int i=0;i<int(nodes.size());++i){
            left[i]=int(nodes[i].deps.size());
            for(int d:nodes[i].deps)children[d].push_back(i);
            if(!left[i])ready.push_back(i);
        }
        std::mt19937 rng(seed);int finished=0;
        while(!ready.empty()){
            size_t at=seed?rng()%ready.size():ready.size()-1;
            int i=ready[at];ready[at]=ready.back();ready.pop_back();
            if(nodes[i].op)nodes[i].op();
            ++finished;
            for(int c:children[i])if(!--left[c])ready.push_back(c);
        }
        need(finished==int(nodes.size()),"pipeline DAG cycle");
    }
};
inline Graph* graph=nullptr;
inline int worker=0;
inline uint64_t zeroWords=0,dmaReadWords=0,storeWords=0,zeroCalls=0;
inline int fault=0; // Oracle sensitivity checks; never present in the kernel.
inline int packedAll=0,waitedAll=0,releasedCube=0;
struct Event {bool allocated=false;int node=-1;};
inline std::array<Event,16> events{};
inline void resetWorker(){events={};packedAll=waitedAll=releasedCube=0;}
}

namespace AscendC {
enum class TPosition {VECCALC};
enum class HardEvent {MTE3_V,V_MTE2,MTE2_MTE3,V_MTE3};
using TEventID=int;
template<class T>struct LocalTensor {
    T* base=nullptr;int64_t size=0,offset=0;
    LocalTensor operator[](int64_t n)const{auto r=*this;r.offset+=n;need(r.offset>=0&&r.offset<=size,"UB slice");return r;}
    void check(int64_t at)const{need(at>=0&&offset+at<size,"UB access outside allocation");}
    T read(int64_t at)const{check(at);return base[offset+at];}
    void write(int64_t at,T v)const{check(at);base[offset+at]=v;}
};
template<class T>struct GlobalTensor {
    T* base=nullptr;int64_t size=0,offset=0;
    void SetGlobalBuffer(T* p,int64_t n){base=p;size=n;offset=0;}
    GlobalTensor operator[](int64_t n)const{auto r=*this;r.offset+=n;need(r.offset>=0&&r.offset<=size,"GM slice");return r;}
    T read(int64_t at)const{need(at>=0&&offset+at<size,"GM read outside tensor");return base[offset+at];}
    void write(int64_t at,T v)const{need(at>=0&&offset+at<size,"GM write outside tensor");base[offset+at]=v;}
};
template<TPosition P>struct TBuf {
    std::vector<half> memory;
    template<class T>LocalTensor<T> Get(){static_assert(sizeof(T)==2);return {reinterpret_cast<T*>(memory.data()),int64_t(memory.size()),0};}
};
struct TPipe {
    template<TPosition P>void InitBuffer(TBuf<P>& b,int bytes){
        need(bytes%2==0,"odd UB allocation");b.memory.resize(bytes/2);
        for(auto& x:b.memory)x.bits=0xa5a5; // Intentionally dirty slots.
    }
    template<HardEvent H>TEventID AllocEventID(){
        static_assert(H==HardEvent::MTE3_V);
        for(int i=0;i<int(Model::events.size());++i)if(!Model::events[i].allocated){Model::events[i]={true,-1};return i;}
        throw std::runtime_error("event exhaustion");
    }
    template<HardEvent H>void ReleaseEventID(int id){
        need(Model::events[id].allocated&&Model::events[id].node<0,"undrained event credit");Model::events[id]={};
    }
};
template<HardEvent H>void SetFlag(int id){
    static_assert(H==HardEvent::MTE3_V);
    auto& e=Model::events[id];need(e.allocated&&e.node<0,"event credit overwrite");e.node=Model::graph->push(2);
}
template<HardEvent H>void WaitFlag(int id){
    static_assert(H==HardEvent::MTE3_V);
    auto& e=Model::events[id];need(e.allocated&&e.node>=0,"wait without event");Model::graph->push(0,{},e.node);e.node=-1;
}
inline int GetBlockIdx(){return Model::worker;}
template<int Mode,int Pipe>void CrossCoreSetFlag(uint16_t id){
    static_assert(Pipe==PIPE_MTE3);
    if constexpr(Mode==0){need(id==0&&!Model::packedAll,"PACK_ALL sequence");Model::packedAll=1;}
    else {static_assert(Mode==2);need(id==2&&Model::waitedAll&&!Model::releasedCube,"PACK_TO_CUBE sequence");Model::releasedCube=1;}
    Model::graph->push(2);
}
template<int Mode>void CrossCoreWaitFlag(uint16_t id){
    static_assert(Mode==0);need(id==0&&Model::packedAll&&!Model::waitedAll,"PACK_ALL wait sequence");Model::waitedAll=1;
    // Cross-worker timing is not emulated. Every independent worker is drained
    // before the full padded tensors are compared with the oracle.
}
struct DataCopyExtParams {uint16_t blockCount;uint32_t blockLen,srcStride,dstStride,rsv;};
template<class T>struct DataCopyPadExtParams {bool isPad;uint8_t leftPadding,rightPadding;T paddingValue;};
template<class T>void Duplicate(LocalTensor<T> dst,const T& v,const int32_t& count){
    need(count>0&&dst.offset%16==0,"Duplicate count/alignment");
    Model::zeroWords+=count;++Model::zeroCalls;
    Model::graph->push(0,[=]{if(Model::fault==2)return;for(int i=0;i<count;++i)dst.write(i,v);});
}
template<class T,bool SetMask=true>void Duplicate(LocalTensor<T> dst,const T& v,uint64_t mask,uint8_t repeat,uint16_t blk,uint8_t stride){
    need(SetMask&&mask>0&&mask<=128&&repeat>0&&dst.offset%16==0,"Duplicate mask/repeat/alignment");
    Model::zeroWords+=mask*repeat;++Model::zeroCalls;
    Model::graph->push(0,[=]{
        if(Model::fault==1)return;
        for(int r=0;r<repeat;++r)for(uint64_t i=0;i<mask;++i)
            dst.write(int64_t(r)*stride*16+(i/16)*blk*16+i%16,v);
    });
}
template<class T>void DataCopyPad(LocalTensor<T> dst,GlobalTensor<T> src,DataCopyExtParams cp,DataCopyPadExtParams<T> pd){
    need(sizeof(T)==2&&cp.blockCount>0&&cp.blockLen%2==0&&cp.srcStride%2==0,"DMA parameter");
    need(pd.isPad&&pd.leftPadding==0&&pd.rightPadding<=15,"unexpected padding");
    const int words=cp.blockLen/2;
    need((words+pd.rightPadding)%16==0,"explicit padding leaves dummy bytes");
    const int pitch=((words+pd.rightPadding+15)/16+cp.dstStride)*16;
    Model::dmaReadWords+=uint64_t(cp.blockCount)*words;
    Model::graph->push(1,[=]{
        for(int row=0;row<cp.blockCount;++row){
            for(int i=0;i<words;++i)dst.write(int64_t(row)*pitch+i,src.read(int64_t(row)*(words+cp.srcStride/2)+i));
            for(int i=0;i<pd.rightPadding;++i)dst.write(int64_t(row)*pitch+words+i,pd.paddingValue);
        }
    });
}
template<class T>void DataCopy(GlobalTensor<T> dst,LocalTensor<T> src,int words){
    need(words>0&&words%16==0&&dst.offset%16==0&&src.offset%16==0,"aligned output copy");
    Model::storeWords+=words;
    Model::graph->push(2,[=]{for(int i=0;i<words;++i)dst.write(i,src.read(i));});
}
}
namespace bmms71 {
template<AscendC::HardEvent H>void Fence(AscendC::TPipe&){
    using E=AscendC::HardEvent;
    if constexpr(H==E::V_MTE2)Model::graph->push(1,{},Model::graph->tail[0]);
    else if constexpr(H==E::MTE2_MTE3)Model::graph->push(2,{},Model::graph->tail[1]);
    else if constexpr(H==E::V_MTE3)Model::graph->push(2,{},Model::graph->tail[0]);
    else static_assert(H==E::V_MTE2||H==E::MTE2_MTE3||H==E::V_MTE3,"unexpected fence");
}
}

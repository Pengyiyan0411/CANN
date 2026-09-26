// CPU storage-layout and arithmetic model ONLY. Not an NPU/CANN simulator.
// The producer's real C++ is executed against explicit 16x16 model layouts.
// Real instruction legality, event visibility and performance remain untested.
#pragma once
#include "cpu_shim.hpp"

enum class QuantMode_t { NoQuant };
namespace AscendC {
using TEventID = int;
struct Nd2NzParams {
    int ndNum=1,nValue=0,dValue=0,srcDValue=0;
    int dstNzC0Stride=0,dstNzNStride=1,srcNdMatrixStride=0,dstNzMatrixStride=0;
};
struct LoadData2DParams {
    int startIndex=0,repeatTimes=0,srcStride=1,dstGap=0;
    bool ifTranspose=false;
};
struct MmadParams { int m=0,n=0,k=0; bool cmatrixInitVal=false; };
struct FixpipeParamsV220 {
    int nSize=0,mSize=0,srcStride=0,dstStride=0,ndNum=1;
    QuantMode_t quantPre=QuantMode_t::NoQuant;
};
template<class T>void DataCopy(LocalTensor<T>d,GlobalTensor<T>s,Nd2NzParams p){
    Mock::need(p.ndNum==1&&p.nValue>0&&p.dValue>0,"unsupported ND2NZ model shape");
    Mock::need(p.nValue%16==0&&p.dValue%16==0&&p.dstNzNStride==1,"ND2NZ model requires aligned extents");
    for(int r=0;r<p.nValue;++r)for(int c=0;c<p.dValue;++c)
        d.SetValue((c/16)*p.dstNzC0Stride*16+r*16+c%16,s.GetValue(r*p.srcDValue+c));
}
template<class T>void LoadData(LocalTensor<T>d,LocalTensor<T>s,LoadData2DParams p){
    Mock::need(p.repeatTimes>0&&p.repeatTimes<=255&&p.srcStride>0,"invalid LoadData model params");
    for(int block=0;block<p.repeatTimes;++block)for(int r=0;r<16;++r)for(int c=0;c<16;++c){
        int src=(p.startIndex+block*p.srcStride)*256+r*16+c;
        int dst=block*(1+p.dstGap)*256+(p.ifTranspose?c*16+r:r*16+c);
        d.SetValue(dst,s.GetValue(src));
    }
}
template<class T>void Mmad(LocalTensor<float>c,LocalTensor<T>a,LocalTensor<T>b,MmadParams p){
    Mock::need(p.m%16==0&&p.n%16==0&&p.k%16==0,"unaligned Mmad model dimensions");
    for(int m=0;m<p.m;++m)for(int n=0;n<p.n;++n){
        int ci=(n/16)*p.m*16+m*16+n%16;
        float v=p.cmatrixInitVal?0:c.GetValue(ci);
        for(int k=0;k<p.k;++k){
            int ai=((m/16)*(p.k/16)+k/16)*256+(m%16)*16+k%16;
            int bi=((k/16)*(p.n/16)+n/16)*256+(n%16)*16+k%16;
            v=std::fma(float(a.GetValue(ai)),float(b.GetValue(bi)),v);
        }
        c.SetValue(ci,v);
    }
}
template<class D,class S>void Fixpipe(GlobalTensor<D>d,LocalTensor<S>s,FixpipeParamsV220 p){
    Mock::need(p.ndNum==1&&p.srcStride>=p.mSize&&p.dstStride>=p.nSize,"invalid Fixpipe model strides");
    for(int m=0;m<p.mSize;++m)for(int n=0;n<p.nSize;++n)
        d.SetValue(m*p.dstStride+n,D(s.GetValue((n/16)*p.srcStride*16+m*16+n%16)));
}
}

"""N256 partial-B residency: keep K512 cached, stream the rest with independent A/B stages."""
from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V12';lab=root/'V12_npu_lab/case12_k1_20261001'
out=root/'V12_npu_lab/results/case12_wide_load_20261001'
base=(v/'v12_baseline_r41.asc').read_bytes().decode()
mod=(lab/'r59_module.asc').read_bytes().decode().replace('1259','1263')
mod=mod.replace('TM=64,TN=64,AM=128,BN=128,K1=256,K0=64,MACRO_ELEMS=AM*BN','TM=64,TN=128,AM=128,BN=256,K1=256,BK1=128,CACHE_K=512,K0=64,MACRO_ELEMS=AM*BN')
mod=mod.replace('32768ULL+32+256','65536ULL+32+256')
start=mod.index('template<class T,bool TA,bool TB>');stop=mod.index('class RowMaxConsumer',start)
producer=r'''template<class T,bool TA,bool TB>
class MacroMmadProducer {
    AscendC::TPipe* pipe_;Plan p;
    AscendC::GlobalTensor<T> a,b;
    AscendC::GlobalTensor<float> ring;
    AscendC::TBuf<AscendC::TPosition::A1> a1Buf;
    AscendC::TBuf<AscendC::TPosition::B1> b1Buf;
    AscendC::TBuf<AscendC::TPosition::A2> a2Buf;
    AscendC::TBuf<AscendC::TPosition::B2> b2Buf;
    AscendC::TBuf<AscendC::TPosition::CO1> cBuf;
    AscendC::TEventID aReady[2],aFree[2],bReady[2],bFree[2],l0Ready[2],l0Free[2],cReady,cFree;
    int seq=0;bool prefetched=false,cPending=false;

    __aicore__ inline void LoadA(int m0,int ar,int k0,int s){
        auto dst=a1Buf.template Get<T>()[s*AM*K1];
        AscendC::Nd2NzParams q{};q.ndNum=1;q.nValue=TA?K1:ar;q.dValue=TA?ar:K1;
        q.srcDValue=TA?p.M:p.K;q.dstNzC0Stride=TA?K1:ar;q.dstNzNStride=1;
        const int64_t off=TA?int64_t(k0)*p.M+m0:int64_t(m0)*p.K+k0;
        AscendC::DataCopy(dst,a[off],q);
        AscendC::SetFlag<AscendC::HardEvent::MTE2_MTE1>(aReady[s]);
    }
    __aicore__ inline void LoadB(int n0,int br,int k0,int s,bool seed){
        static_assert(!TB,"physical KxN B required");
        if(k0>=CACHE_K||seed){
            const int offset=k0<CACHE_K?k0*BN:CACHE_K*BN+s*BK1*BN;
            AscendC::Nd2NzParams q{};q.ndNum=1;q.nValue=BK1;q.dValue=br;
            q.srcDValue=p.N;q.dstNzC0Stride=BK1;q.dstNzNStride=1;
            AscendC::DataCopy(b1Buf.template Get<T>()[offset],b[int64_t(k0)*p.N+n0],q);
        }
        AscendC::SetFlag<AscendC::HardEvent::MTE2_MTE1>(bReady[s]);
    }
    __aicore__ inline void LoadL0(int ar,int br,int ki,int kk,int saSlot,int sbSlot,int s0){
        const int ak=(ki%2)*BK1+kk,bk=ki*BK1;
        auto sa=a1Buf.template Get<T>()[saSlot*AM*K1];
        auto sb=b1Buf.template Get<T>()[bk<CACHE_K?bk*BN:CACHE_K*BN+sbSlot*BK1*BN];
        auto da=a2Buf.template Get<T>()[s0*AM*K0];auto db=b2Buf.template Get<T>()[s0*K0*BN];
        AscendC::LoadData2DParams qa{};qa.repeatTimes=K0/16;qa.srcStride=TA?1:ar/16;qa.ifTranspose=TA;
        for(int i=0;i<ar/16;++i){
            const int off=TA?i*K1*16+ak*16:(ak/16)*ar*16+i*256;
            AscendC::LoadData(da[i*K0*16],sa[off],qa);
        }
        AscendC::LoadData2DParams qb{};qb.repeatTimes=br/16;qb.srcStride=BK1/16;qb.ifTranspose=true;
        for(int j=0;j<K0/16;++j)AscendC::LoadData(db[j*br*16],sb[(kk+j*16)*16],qb);
        AscendC::SetFlag<AscendC::HardEvent::MTE1_M>(l0Ready[s0]);
        AscendC::WaitFlag<AscendC::HardEvent::MTE1_M>(l0Ready[s0]);
    }
    __aicore__ inline void Macro(int group,int m0,int n0,int ar,int br,int nextM,int nextAr,bool hasNext,bool seed){
        if(!prefetched){LoadA(m0,ar,0,0);LoadB(n0,br,0,0,seed);}
        prefetched=false;int count=0;
        for(int ki=0;ki<1536/BK1;++ki){
            const int ai=ki/2,as=ai&1,bs=ki&1;
            if(ki%2==0)AscendC::WaitFlag<AscendC::HardEvent::MTE2_MTE1>(aReady[as]);
            AscendC::WaitFlag<AscendC::HardEvent::MTE2_MTE1>(bReady[bs]);
            // A is staged independently every K256; no half-aligned A copies.
            if(ki%2==1){
                const int next=as^1;
                if(ai+1<1536/K1){
                    if(ai>=1)AscendC::WaitFlag<AscendC::HardEvent::MTE1_MTE2>(aFree[next]);
                    LoadA(m0,ar,(ai+1)*K1,next);
                }else if(hasNext){
                    AscendC::WaitFlag<AscendC::HardEvent::MTE1_MTE2>(aFree[next]);
                    LoadA(nextM,nextAr,0,next);
                }
            }
            if(ki+1<1536/BK1){
                const int next=bs^1;
                if(ki>=1)AscendC::WaitFlag<AscendC::HardEvent::MTE1_MTE2>(bFree[next]);
                LoadB(n0,br,(ki+1)*BK1,next,seed);
            }else if(hasNext){
                AscendC::WaitFlag<AscendC::HardEvent::MTE1_MTE2>(bFree[0]);
                LoadB(n0,br,0,0,false);prefetched=true;
            }
            for(int kk=0;kk<BK1;kk+=K0){
                const int s0=count&1;
                if(count>=2)AscendC::WaitFlag<AscendC::HardEvent::M_MTE1>(l0Free[s0]);
                LoadL0(ar,br,ki,kk,as,bs,s0);
                if(kk+K0==BK1){
                    AscendC::SetFlag<AscendC::HardEvent::MTE1_MTE2>(bFree[bs]);
                    if(ki%2==1)AscendC::SetFlag<AscendC::HardEvent::MTE1_MTE2>(aFree[as]);
                }
                if(cPending){AscendC::WaitFlag<AscendC::HardEvent::FIX_M>(cFree);cPending=false;}
                AscendC::MmadParams q{};q.m=ar;q.n=br;q.k=K0;q.cmatrixInitVal=(count==0);
                AscendC::Mmad(cBuf.template Get<float>(),a2Buf.template Get<T>()[s0*AM*K0],b2Buf.template Get<T>()[s0*K0*BN],q);
                if((ar/16)*(br/16)<10)AscendC::PipeBarrier<PIPE_M>();
                AscendC::SetFlag<AscendC::HardEvent::M_MTE1>(l0Free[s0]);++count;
            }
        }
        for(int s=hasNext?1:0;s<2;++s){
            AscendC::WaitFlag<AscendC::HardEvent::MTE1_MTE2>(aFree[s]);
            AscendC::WaitFlag<AscendC::HardEvent::MTE1_MTE2>(bFree[s]);
        }
        for(int s=0;s<2;++s)AscendC::WaitFlag<AscendC::HardEvent::M_MTE1>(l0Free[s]);
        AscendC::SetFlag<AscendC::HardEvent::M_FIX>(cReady);AscendC::WaitFlag<AscendC::HardEvent::M_FIX>(cReady);
        const int slot=seq&1;if(seq>=2)AscendC::CrossCoreWaitFlag<0x2>(FREE+slot);
        AscendC::FixpipeParamsV220 q{};q.nSize=br;q.mSize=ar;q.srcStride=ar;q.dstStride=BN;q.ndNum=1;q.quantPre=QuantMode_t::NoQuant;
        AscendC::Fixpipe<float,float>(ring[(int64_t(group)*2+slot)*MACRO_ELEMS],cBuf.template Get<float>(),q);
        AscendC::SetFlag<AscendC::HardEvent::FIX_M>(cFree);cPending=true;
        AscendC::CrossCoreSetFlag<0x2,PIPE_FIX>(READY+slot);++seq;
    }
public:
    __aicore__ inline void Init(GM_ADDR x,GM_ADDR z,GM_ADDR r,const Plan& plan,AscendC::TPipe* pipe){
        p=plan;pipe_=pipe;
        for(int s=0;s<2;++s){
            aReady[s]=pipe->AllocEventID<AscendC::HardEvent::MTE2_MTE1>();bReady[s]=pipe->AllocEventID<AscendC::HardEvent::MTE2_MTE1>();
            aFree[s]=pipe->AllocEventID<AscendC::HardEvent::MTE1_MTE2>();bFree[s]=pipe->AllocEventID<AscendC::HardEvent::MTE1_MTE2>();
            l0Ready[s]=pipe->AllocEventID<AscendC::HardEvent::MTE1_M>();l0Free[s]=pipe->AllocEventID<AscendC::HardEvent::M_MTE1>();
        }
        cReady=pipe->AllocEventID<AscendC::HardEvent::M_FIX>();cFree=pipe->AllocEventID<AscendC::HardEvent::FIX_M>();
        a.SetGlobalBuffer(reinterpret_cast<__gm__ T*>(x),int64_t(p.M)*p.K);b.SetGlobalBuffer(reinterpret_cast<__gm__ T*>(z),int64_t(p.K)*p.N);
        ring.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(r),int64_t(p.blocks)*2*MACRO_ELEMS);
        pipe->InitBuffer(a1Buf,2*AM*K1*sizeof(T));pipe->InitBuffer(b1Buf,(CACHE_K+2*BK1)*BN*sizeof(T));
        pipe->InitBuffer(a2Buf,2*AM*K0*sizeof(T));pipe->InitBuffer(b2Buf,2*K0*BN*sizeof(T));pipe->InitBuffer(cBuf,MACRO_ELEMS*4);
    }
    __aicore__ inline void Process(){
        const int group=AscendC::GetBlockIdx(),last=(group+1)*p.totalTiles/p.blocks;int first=group*p.totalTiles/p.blocks;
        while(first<last){
            const int nt=first/p.mTiles,mt=first%p.mTiles,end=MinI(last,(nt+1)*p.mTiles);
            const int mBegin=mt*AM,mEnd=MinI((end-nt*p.mTiles)*AM,p.M),n0=nt*BN,br=MinI(BN,p.N-n0);
            for(int m=mBegin;m<mEnd;m+=AM){
                const bool next=m+AM<mEnd;
                Macro(group,m,n0,MinI(AM,mEnd-m),br,m+AM,next?MinI(AM,mEnd-m-AM):0,next,m==mBegin);
            }
            first=end;
        }
        for(int s=0;s<MinI(2,seq);++s)AscendC::CrossCoreWaitFlag<0x2>(FREE+s);
        if(cPending)AscendC::WaitFlag<AscendC::HardEvent::FIX_M>(cFree);
        for(int s=0;s<2;++s){
            pipe_->ReleaseEventID<AscendC::HardEvent::MTE2_MTE1>(aReady[s]);pipe_->ReleaseEventID<AscendC::HardEvent::MTE2_MTE1>(bReady[s]);
            pipe_->ReleaseEventID<AscendC::HardEvent::MTE1_MTE2>(aFree[s]);pipe_->ReleaseEventID<AscendC::HardEvent::MTE1_MTE2>(bFree[s]);
            pipe_->ReleaseEventID<AscendC::HardEvent::MTE1_M>(l0Ready[s]);pipe_->ReleaseEventID<AscendC::HardEvent::M_MTE1>(l0Free[s]);
        }
        pipe_->ReleaseEventID<AscendC::HardEvent::M_FIX>(cReady);pipe_->ReleaseEventID<AscendC::HardEvent::FIX_M>(cFree);
    }
};

'''
mod=mod[:start]+producer+mod[stop:]
old='''            const AscendC::BinaryRepeatParams rp{1,1,1,16,16,16};
            AscendC::Max(c,c,c[64],64,vr,rp);AscendC::PipeBarrier<PIPE_V>();
            AscendC::WholeReduceMax(rows,c,64,vr,1,1,16,AscendC::ReduceOrder::ORDER_ONLY_VALUE);'''
new='''            const AscendC::BinaryRepeatParams rp{1,1,1,32,32,32};
            AscendC::Max(c,c,c[128],64,vr,rp);AscendC::PipeBarrier<PIPE_V>();
            AscendC::Max(c[64],c[64],c[192],64,vr,rp);AscendC::PipeBarrier<PIPE_V>();
            AscendC::Max(c,c,c[64],64,vr,rp);AscendC::PipeBarrier<PIPE_V>();
            AscendC::WholeReduceMax(rows,c,64,vr,1,1,32,AscendC::ReduceOrder::ORDER_ONLY_VALUE);'''
assert old in mod;mod=mod.replace(old,new)
hook='    if(bmms1263::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
pos=base.index('extern "C" void run_kernel(');src=base[:pos]+mod+base[pos:]
pos=src.index('    if(bmms1241::TryLaunch');src=src[:pos]+hook+src[pos:]
assert src.replace(mod,'',1).replace(hook,'',1)==base
name='v12_r63_case12_wide_partial_b.asc';assert not(v/name).exists()
for p in [v/name,lab/'r63.asc']:p.write_bytes(src.encode())
(lab/'r63_module.asc').write_bytes(mod.encode())
meta=dict(version='v12_r63',parent='v12_baseline_r41.asc',file=name,sha256=hashlib.sha256(src.encode()).hexdigest(),status='pending audit and NPU validation',
          change='N256 flat N-major runs; K512 of B cached across M; independent A256 double buffer and B128 double buffer; original K64 accumulation',
          new_device_entries=4,parent_byte_recovery=True,L1_bytes=524288,L0A_bytes=32768,L0B_bytes=65536,L0C_bytes=131072)
(v/'v12_r63_manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
cm=(lab/'CMakeLists.txt').read_text().replace('r61 r62)','r61 r62 r63)');(lab/'CMakeLists.txt').write_bytes(cm.encode())
script=(lab/'check_r62.sh').read_text().replace('r62','r63').replace('R62','R63')
(lab/'check_r63.sh').write_text(script,encoding='utf-8',newline='\n')
print(json.dumps(meta))

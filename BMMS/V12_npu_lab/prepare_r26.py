from pathlib import Path
import json,hashlib
r=Path(__file__).resolve().parents[1];o=r/'BMMS_V12';h=r/'V12_npu_lab/harness'
raw=(o/'v12_r25_dense_macro_store.asc').read_bytes().decode('utf-8').replace('1225','1226')
a=raw.index('class RowMaxConsumer {',raw.index('// BMMS1226_BEGIN'));b=raw.index('\n};',a)+len('\n};')
consumer=r'''class RowMaxConsumer {
    Plan p;AscendC::TPipe* pipe_;
    AscendC::GlobalTensor<float> ring,part,out;
    AscendC::TQue<AscendC::TPosition::VECIN,1> cq;
    AscendC::TQue<AscendC::TPosition::VECOUT,1> oq;
    AscendC::TBuf<AscendC::TPosition::VECCALC> rowBuf,sumBuf;
    AscendC::TBuf<AscendC::TPosition::VECOUT> runningBuf;
    AscendC::TBuf<AscendC::TPosition::VECIN> mergedBuf,tmpBuf;
public:
    __aicore__ inline void Init(GM_ADDR r,GM_ADDR pt,GM_ADDR y,const Plan& plan,AscendC::TPipe* pipe){
        p=plan;pipe_=pipe;
        ring.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(r),int64_t(p.blocks)*2*MACRO_ELEMS);
        part.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(pt),int64_t(p.B)*p.pN*p.M);
        out.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(y),p.B);
        pipe->InitBuffer(cq,1,(AM/2)*BN*4);pipe->InitBuffer(oq,1,32);
        pipe->InitBuffer(rowBuf,(AM/2)*4);pipe->InitBuffer(runningBuf,(AM/2)*4);
        pipe->InitBuffer(mergedBuf,p.M*4);pipe->InitBuffer(tmpBuf,p.M*4);pipe->InitBuffer(sumBuf,p.M*4);
    }
    __aicore__ inline void Process(){
        const int worker=AscendC::GetBlockIdx(),group=worker/2,sub=worker%2;
        const int perBatch=p.pM*p.pN;
        int seq=0;auto rows=rowBuf.Get<float>(),run=runningBuf.Get<float>();
        for(int task=group;task<p.tasks;task+=p.blocks){
            const int batch=task/perBatch,slot=task-batch*perBatch,ms=slot/p.pN,ns=slot-ms*p.pN;
            const int mt0=ms*p.mTiles/p.pM,mt1=(ms+1)*p.mTiles/p.pM;
            const int nt0=ns*p.nTiles/p.pN,nt1=(ns+1)*p.nTiles/p.pN;
            const int mBegin=mt0*AM,mEnd=MinI(mt1*AM,p.M),nBegin=nt0*BN,nEnd=MinI(nt1*BN,p.N);
            for(int mBase=mBegin;mBase<mEnd;mBase+=AM){
                const int ar=MinI(AM,mEnd-mBase),vr=ar/2;
                AscendC::Duplicate(run,bmmmaxsum_v43::NEG_INF,vr);AscendC::PipeBarrier<PIPE_V>();
                for(int nBase=nBegin;nBase<nEnd;nBase+=BN){
                    const int br=MinI(BN,nEnd-nBase),ringSlot=seq&1;
                    AscendC::CrossCoreWaitFlag<0x2>(READY+ringSlot);
                    auto c=cq.AllocTensor<float>();
                    AscendC::Duplicate(c,bmmmaxsum_v43::NEG_INF,vr*BN);
                    bmms71::Fence<AscendC::HardEvent::V_MTE2>(*pipe_);
                    const int64_t off=(int64_t(group)*2+ringSlot)*MACRO_ELEMS+sub*vr*BN;
                    AscendC::DataCopyExtParams cp{static_cast<uint16_t>(vr),uint32_t(br*4),uint32_t((BN-br)*4),uint32_t((BN-br)/8),0};
                    AscendC::DataCopyPadExtParams<float> pd{false,0,0,0.0f};
                    AscendC::DataCopyPad(c,ring[off],cp,pd);cq.EnQue(c);c=cq.DeQue<float>();
                    // The entire half-macro is in UB. Its ring slot can now be reused.
                    AscendC::CrossCoreSetFlag<0x2,PIPE_MTE2>(FREE+ringSlot);
                    AscendC::BinaryRepeatParams rp{1,1,1,32,32,32};
                    AscendC::Max(c,c,c[128],64,vr,rp);AscendC::PipeBarrier<PIPE_V>();
                    AscendC::Max(c[64],c[64],c[192],64,vr,rp);AscendC::PipeBarrier<PIPE_V>();
                    AscendC::Max(c,c,c[64],64,vr,rp);AscendC::PipeBarrier<PIPE_V>();
                    AscendC::WholeReduceMax(rows,c,64,vr,1,1,32,AscendC::ReduceOrder::ORDER_ONLY_VALUE);
                    AscendC::PipeBarrier<PIPE_V>();
                    AscendC::Max(run,run,rows,vr);AscendC::PipeBarrier<PIPE_V>();
                    cq.FreeTensor(c);++seq;
                }
                bmms71::Fence<AscendC::HardEvent::V_MTE3>(*pipe_);
                const int64_t dst=(int64_t(batch)*p.pN+ns)*p.M+mBase+sub*vr;
                AscendC::DataCopy(part[dst],run,vr);
                bmms71::Fence<AscendC::HardEvent::MTE3_V>(*pipe_);
            }
        }
        bmms71::Fence<AscendC::HardEvent::MTE3_MTE2>(*pipe_);AscendC::SyncAll<true>();
        auto merged=mergedBuf.Get<float>(),tmp=tmpBuf.Get<float>();
        for(int batch=worker;batch<p.B;batch+=2*p.blocks){
            const int64_t start=int64_t(batch)*p.pN*p.M;
            AscendC::DataCopy(merged,part[start],p.M);bmms71::Fence<AscendC::HardEvent::MTE2_V>(*pipe_);
            for(int ns=1;ns<p.pN;++ns){
                AscendC::DataCopy(tmp,part[start+int64_t(ns)*p.M],p.M);bmms71::Fence<AscendC::HardEvent::MTE2_V>(*pipe_);
                AscendC::Max(merged,merged,tmp,p.M);bmms71::Fence<AscendC::HardEvent::V_MTE2>(*pipe_);
            }
            auto yy=oq.AllocTensor<float>();AscendC::ReduceSum(yy,merged,sumBuf.Get<float>(),p.M);
            oq.EnQue(yy);yy=oq.DeQue<float>();AscendC::DataCopyExtParams oc{1,4,0,0,0};
            AscendC::DataCopyPad(out[batch],yy,oc);oq.FreeTensor(yy);bmms71::Fence<AscendC::HardEvent::V_MTE2>(*pipe_);
        }
    }
};'''
raw=raw[:a]+consumer+raw[b:];data=raw.encode();name='v12_r26_dense_macro_consumer.asc'
(o/name).write_bytes(data);(h/'r26.asc').write_bytes(data)
m=dict(version='v12_r26',file=name,sha256=hashlib.sha256(data).hexdigest(),parent='v12_baseline_r19.asc',
    parent_sha256=hashlib.sha256((o/'v12_baseline_r19.asc').read_bytes()).hexdigest(),status='experimental; validation pending',
    change='r25 full-macro MMAD/store plus one half-macro read per AIV; 256-column max reduction; same original plan and aligned-pitch domain')
(o/'v12_r26_manifest.json').write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8')
(h/'event_bench_r26.asc').write_text((h/'event_bench_r25.asc').read_text(encoding='utf-8').replace('1225','1226'),encoding='utf-8',newline='\n')
cm=h/'CMakeLists.txt';t=cm.read_text(encoding='utf-8')
if 'add_executable(bench_r26 ' not in t:t+='\n'+t[t.index('add_executable(bench_r25 '):].replace('r25','r26')
cm.write_text(t,encoding='utf-8',newline='\n')
print(name,m['sha256'])

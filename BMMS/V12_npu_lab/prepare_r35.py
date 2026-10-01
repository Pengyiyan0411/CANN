from pathlib import Path
import hashlib,json
r=Path(__file__).resolve().parents[1];o=r/'BMMS_V12';h=r/'V12_npu_lab/harness'
base=(o/'v12_baseline_r33.asc').read_bytes();s=base.decode()
a=s.index('// BMMS1230_BEGIN');b=s.index('// BMMS1230_END',a)+len('// BMMS1230_END')
mod=s[a:b].replace('1230','1235')
mod=mod.replace('using Plan=bmms11r2::Plan;', 'using Plan=bmms83::NativePlan;')
mod=mod.replace('AM=128,BN=256,K1=256,K0=64,MACRO_ELEMS=4*TM*TN',
                'AM=256,BN=64,K1=128,K0=128,MACRO_ELEMS=AM*BN')
a=mod.index('static inline bool Eligible');b=mod.index('template<class T,bool TA,bool TB>',a)
mod=mod[:a]+'''static inline bool Select(const Plan& p){return bmms49::Select(p);}
''' +mod[b:]
mod=mod.replace('[s0*AM*K0]','[0]').replace('[s0*K0*BN]','[0]')
mod=mod.replace('2*AM*K0*sizeof(T)','AM*K0*sizeof(T)').replace('2*K0*BN*sizeof(T)','K0*BN*sizeof(T)')
mod=mod.replace('4*TM*TN*sizeof(float)','AM*BN*sizeof(float)')
mod=mod.replace('mBegin=mt0*AM,mEnd=MinI(mt1*AM,p.M),nBegin=nt0*BN,nEnd=MinI(nt1*BN,p.N)',
                'mBegin=mt0*TM,mEnd=MinI(mt1*TM,p.M),nBegin=nt0*TN,nEnd=MinI(nt1*TN,p.N)')
a=mod.index('class RowMaxConsumer {');b=mod.index('} // namespace bmms1235',a)
mod=mod[:a]+'''// Select guarantees one complete N panel. One notification and compact DMA
// replace up to four 64-row tiles without changing the final M sum order.
class RowMaxConsumer {
    Plan p;AscendC::TPipe* pipe_;
    AscendC::GlobalTensor<float> ring,part,out;
    AscendC::TQue<AscendC::TPosition::VECIN,1> cq;
    AscendC::TQue<AscendC::TPosition::VECOUT,1> oq;
    AscendC::TBuf<AscendC::TPosition::VECOUT> rowBuf;
    AscendC::TBuf<AscendC::TPosition::VECIN> mergedBuf;
    AscendC::TBuf<AscendC::TPosition::VECCALC> sumBuf;
public:
    __aicore__ inline void Init(GM_ADDR r,GM_ADDR pt,GM_ADDR y,const Plan& plan,AscendC::TPipe* pipe){
        p=plan;pipe_=pipe;
        ring.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(r),int64_t(p.blocks)*2*MACRO_ELEMS);
        part.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(pt),p.M);
        out.SetGlobalBuffer(reinterpret_cast<__gm__ float*>(y),1);
        pipe->InitBuffer(cq,1,(AM/2)*BN*4);pipe->InitBuffer(oq,1,32);
        pipe->InitBuffer(rowBuf,(AM/2)*4);pipe->InitBuffer(mergedBuf,p.M*4);pipe->InitBuffer(sumBuf,p.M*4);
    }
    __aicore__ inline void Process(){
        const int worker=AscendC::GetBlockIdx(),group=worker/2,sub=worker%2;
        int seq=0;auto rows=rowBuf.Get<float>();
        for(int task=group;task<p.tasks;task+=p.blocks){
            const int mBegin=(task*p.mTiles/p.pM)*TM,mEnd=MinI(((task+1)*p.mTiles/p.pM)*TM,p.M);
            for(int m0=mBegin;m0<mEnd;m0+=AM){
                const int ar=MinI(AM,mEnd-m0),vr=ar/2,slot=seq&1;
                AscendC::CrossCoreWaitFlag<0x2>(READY+slot);
                auto c=cq.AllocTensor<float>();
                const int64_t off=(int64_t(group)*2+slot)*MACRO_ELEMS+sub*vr*BN;
                AscendC::DataCopyExtParams cp{static_cast<uint16_t>(vr),uint32_t(p.N*4),uint32_t((BN-p.N)*4),0,0};
                AscendC::DataCopyPadExtParams<float> pd{false,0,0,0.0f};
                AscendC::DataCopyPad(c,ring[off],cp,pd);cq.EnQue(c);c=cq.DeQue<float>();
                AscendC::CrossCoreSetFlag<0x2,PIPE_MTE2>(FREE+slot);
                AscendC::WholeReduceMax(rows,c,p.N,vr,1,1,p.N/8,AscendC::ReduceOrder::ORDER_ONLY_VALUE);
                bmms71::Fence<AscendC::HardEvent::V_MTE3>(*pipe_);
                AscendC::DataCopyExtParams rp{1,uint32_t(vr*4),0,0,0};
                AscendC::DataCopyPad(part[m0+sub*vr],rows,rp);
                bmms71::Fence<AscendC::HardEvent::MTE3_V>(*pipe_);
                cq.FreeTensor(c);++seq;
            }
        }
        bmms71::Fence<AscendC::HardEvent::MTE3_MTE2>(*pipe_);AscendC::SyncAll<true>();
        if(worker==0){
            auto merged=mergedBuf.Get<float>();
            AscendC::DataCopyExtParams mp{1,uint32_t(p.M*4),0,0,0};
            AscendC::DataCopyPadExtParams<float> pd{false,0,0,0.0f};
            AscendC::DataCopyPad(merged,part,mp,pd);
            bmms71::Fence<AscendC::HardEvent::MTE2_V>(*pipe_);
            auto yy=oq.AllocTensor<float>();AscendC::ReduceSum(yy,merged,sumBuf.Get<float>(),p.M);
            oq.EnQue(yy);yy=oq.DeQue<float>();AscendC::DataCopyExtParams oc{1,4,0,0,0};
            AscendC::DataCopyPad(out,yy,oc);oq.FreeTensor(yy);
        }
    }
};
''' +mod[b:]
# Keep the existing host scope and allocation format; the compact ring fits
# inside the original native ring allocation, and partial starts at its old offset.
a=mod.index('static inline bool TryLaunch');b=mod.index('// BMMS1235_END',a)
host=s[s.index('namespace bmms49 {',s.index('#undef BMMS49_KERNEL')):s.index('// BMMS49_END')]
host=host[host.index('static inline bool TryLaunch'):].replace('bmms49','bmms1235').replace('BMMS49','BMMS1235')
mod=mod[:a]+host+mod[b:]
payload=('\n'+mod+'\n\n').encode();ix=base.index(b'extern "C" void run_kernel')
data=base[:ix]+payload+base[ix:]
hook=b'        if(bmms1235::TryLaunch(a,b,y,p,x.dtype,ta,tb,stream))return;\n'
ix=data.index(b'        if(bmms49::TryLaunch');data=data[:ix]+hook+data[ix:]
assert data.replace(payload,b'',1).replace(hook,b'',1)==base
name='v12_r35_native_macro256.asc';(o/name).write_bytes(data);(h/'r35.asc').write_bytes(data)
ev=(h/'event_bench_r33.asc').read_text(encoding='utf-8')
a=ev.index('static bool eligible');b=ev.index('static void launch_direct',a)
ev=ev[:a]+'''static bool eligible(int B,int M,int N,int K,int dt,int cores){
 return (dt==1||dt==2)&&bmms1235::Select(bmms83::MakeNative(B,M,N,K,cores));
}
'''+ev[b:]
ev=ev.replace('bmms11r2::Plan','bmms83::NativePlan').replace('bmms11r2::MakePlan','bmms83::MakeNative')
ev=ev.replace('bmms11r2::RingBytes','bmms83::NativeRingBytes').replace('bmms11r2::WorkspaceBytes(p)','(bmms83::NativeRingBytes(p)+bmms83::NativePartialBytes(p))')
ev=ev.replace('DISPATCH(bmms1233)','DISPATCH(bmms1235)').replace('DISPATCH(bmms11r2)','DISPATCH(bmms49)')
ev=ev.replace('candidate?"r33":"r30"','candidate?"r35":"r33"')
(h/'event_bench_r35.asc').write_text(ev,encoding='utf-8',newline='\n')
cm=h/'CMakeLists.txt';s=cm.read_text(encoding='utf-8')
if 'add_executable(bench_r35 ' not in s:s+='\n'+s[s.index('add_executable(bench_r34 '):].replace('r34','r35')
cm.write_text(s,encoding='utf-8',newline='\n')
meta=dict(version='v12_r35',status='experimental; screening pending',parent='v12_baseline_r33.asc',file=name,sha256=hashlib.sha256(data).hexdigest(),parent_byte_recovery=True,scope='exact bmms49::Select, original native plan',change='up to 256 rows per MMAD/Fixpipe/notification, compact N48/64 consumer; original full-M ReduceSum',L1_bytes=163840,L0A_bytes=65536,L0B_bytes=16384,L0C_bytes=65536)
(o/'v12_r35_manifest.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8');print(json.dumps(meta))

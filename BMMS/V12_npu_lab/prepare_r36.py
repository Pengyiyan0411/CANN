from pathlib import Path
import hashlib,json
r=Path(__file__).resolve().parents[1];o=r/'BMMS_V12';h=r/'V12_npu_lab/harness'
base=(o/'v12_baseline_r33.asc').read_bytes();s=(o/'v12_r35_native_macro256.asc').read_bytes().decode()
a=s.index('// BMMS1235_BEGIN');b=s.index('// BMMS1235_END',a)+len('// BMMS1235_END')
mod=s[a:b].replace('1235','1236').replace('AM=256,BN=64','AM=128,BN=64')
mod=mod.replace('l0Free[2],cReady,cFree;', 'l0Free[2],cReady[2],cFree[2];')
mod=mod.replace('int32_t seq=0;bool cPending=false;', 'int32_t seq=0;')
mod=mod.replace('a2Buf.template Get<T>()[0]', 'a2Buf.template Get<T>()[s0*AM*K0]')
mod=mod.replace('b2Buf.template Get<T>()[0]', 'b2Buf.template Get<T>()[s0*K0*BN]')
a=mod.index('    __aicore__ inline void Macro(');b=mod.index('\npublic:',a)
mod=mod[:a]+'''    __aicore__ inline void Macro(int group,int batch,int m0,int n0,int ar,int br,int nextM,int nextN,int nextAr,int nextBr,bool hasNext){
        // K is exactly 128 in this route. Both L0 operand slots and both
        // accumulators remain owned until their real M/FIX consumers finish.
        const int s1=l1Start,slot=seq&1;
        if(!l1Prefetched)LoadStage(batch,m0,n0,ar,br,0,128,s1);
        l1Prefetched=false;
        AscendC::WaitFlag<AscendC::HardEvent::MTE2_MTE1>(l1Ready[s1]);
        if(hasNext){
            const int next=s1^1;
            LoadStage(batch,nextM,nextN,nextAr,nextBr,0,128,next);
            l1Start=next;l1Prefetched=true;
        }
        if(seq>=2)AscendC::WaitFlag<AscendC::HardEvent::M_MTE1>(l0Free[slot]);
        LoadL0(ar,br,128,0,128,s1,slot);
        AscendC::SetFlag<AscendC::HardEvent::MTE1_MTE2>(l1Free[s1]);
        if(seq>=2)AscendC::WaitFlag<AscendC::HardEvent::FIX_M>(cFree[slot]);
        auto aa=a2Buf.template Get<T>()[slot*AM*K0];
        auto bb=b2Buf.template Get<T>()[slot*K0*BN];
        auto cc=cBuf.template Get<float>()[slot*AM*BN];
        AscendC::MmadParams q{};q.m=ar;q.n=br;q.k=128;q.cmatrixInitVal=true;
        AscendC::Mmad(cc,aa,bb,q);
        AscendC::SetFlag<AscendC::HardEvent::M_MTE1>(l0Free[slot]);
        AscendC::WaitFlag<AscendC::HardEvent::MTE1_MTE2>(l1Free[s1]);
        if(!hasNext)l1Start=0;
        AscendC::SetFlag<AscendC::HardEvent::M_FIX>(cReady[slot]);
        AscendC::WaitFlag<AscendC::HardEvent::M_FIX>(cReady[slot]);
        if(seq>=2)AscendC::CrossCoreWaitFlag<0x2>(FREE+slot);
        AscendC::FixpipeParamsV220 f{};f.nSize=br;f.mSize=ar;f.srcStride=ar;
        f.dstStride=BN;f.ndNum=1;f.quantPre=QuantMode_t::NoQuant;
        AscendC::Fixpipe<float,float>(ring[(int64_t(group)*2+slot)*MACRO_ELEMS],cc,f);
        AscendC::SetFlag<AscendC::HardEvent::FIX_M>(cFree[slot]);
        AscendC::CrossCoreSetFlag<0x2,PIPE_FIX>(READY+slot);++seq;
    }
''' +mod[b:]
mod=mod.replace('cReady=pipe->AllocEventID<AscendC::HardEvent::M_FIX>();cFree=pipe->AllocEventID<AscendC::HardEvent::FIX_M>();',
'''for(int s=0;s<2;++s){
            cReady[s]=pipe->AllocEventID<AscendC::HardEvent::M_FIX>();cFree[s]=pipe->AllocEventID<AscendC::HardEvent::FIX_M>();
        }''')
mod=mod.replace('InitBuffer(a2Buf,AM*K0*sizeof(T))','InitBuffer(a2Buf,2*AM*K0*sizeof(T))')
mod=mod.replace('InitBuffer(b2Buf,K0*BN*sizeof(T))','InitBuffer(b2Buf,2*K0*BN*sizeof(T))')
mod=mod.replace('InitBuffer(cBuf,AM*BN*sizeof(float))','InitBuffer(cBuf,2*AM*BN*sizeof(float))')
mod=mod.replace('if(cPending)AscendC::WaitFlag<AscendC::HardEvent::FIX_M>(cFree);',
'''for(int s=0;s<MinI(2,seq);++s){
            AscendC::WaitFlag<AscendC::HardEvent::M_MTE1>(l0Free[s]);
            AscendC::WaitFlag<AscendC::HardEvent::FIX_M>(cFree[s]);
        }''')
mod=mod.replace('pipe_->ReleaseEventID<AscendC::HardEvent::M_FIX>(cReady);pipe_->ReleaseEventID<AscendC::HardEvent::FIX_M>(cFree);',
'''for(int s=0;s<2;++s){
            pipe_->ReleaseEventID<AscendC::HardEvent::M_FIX>(cReady[s]);pipe_->ReleaseEventID<AscendC::HardEvent::FIX_M>(cFree[s]);
        }''')
mod=mod.replace('up to four 64-row tiles','up to two 64-row tiles')
payload=('\n'+mod+'\n\n').encode();ix=base.index(b'extern "C" void run_kernel');data=base[:ix]+payload+base[ix:]
hook=b'        if(bmms1236::TryLaunch(a,b,y,p,x.dtype,ta,tb,stream))return;\n'
ix=data.index(b'        if(bmms49::TryLaunch');data=data[:ix]+hook+data[ix:]
assert data.replace(payload,b'',1).replace(hook,b'',1)==base
name='v12_r36_native_macro128_pingpong.asc';(o/name).write_bytes(data);(h/'r36.asc').write_bytes(data)
ev=(h/'event_bench_r35.asc').read_text(encoding='utf-8').replace('1235','1236').replace('r35','r36')
(h/'event_bench_r36.asc').write_text(ev,encoding='utf-8',newline='\n')
cm=h/'CMakeLists.txt';s=cm.read_text(encoding='utf-8')
if 'add_executable(bench_r36 ' not in s:s+='\n'+s[s.index('add_executable(bench_r35 '):].replace('r35','r36')
cm.write_text(s,encoding='utf-8',newline='\n')
for src,dst in [('screen_r35.sh','screen_r36.sh'),('validate_r35.sh','validate_r36.sh')]:
 (h/dst).write_text((h/src).read_text().replace('r35','r36'),encoding='utf-8',newline='\n')
meta=dict(version='v12_r36',status='experimental; screening pending',parent='v12_baseline_r33.asc',file=name,sha256=hashlib.sha256(data).hexdigest(),parent_byte_recovery=True,scope='exact bmms49::Select, original native plan',change='128-row macro with dual L0 operands and dual L0C, cross-macro L1 prefetch and compact consumer; original M sum',L1_bytes=98304,L0A_bytes=65536,L0B_bytes=32768,L0C_bytes=65536)
(o/'v12_r36_manifest.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8');print(json.dumps(meta))

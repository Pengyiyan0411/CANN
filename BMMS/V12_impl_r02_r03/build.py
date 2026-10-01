from pathlib import Path
import importlib.util,hashlib,json
H=Path(__file__).resolve().parent;ROOT=H.parent;OUT=ROOT/'BMMS_V12'
BASE=OUT/'V12_BASELINE_R52.asc';SHA='3c66689f4a38b4b6b02aa92547b39065a55d3fdfbcf767d6a53a4618f34cc284'
spec=importlib.util.spec_from_file_location('helpers',ROOT/'V11_impl_r50/build.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
write,once,between,function,host=old.write,old.once,old.between,old.function,old.host
NAMES={2:'v12_r02_case9_10_a_resident',3:'v12_r03_case2_static_k'}
def producer(src):
    start=src.index('template<class T,bool TA,bool TB>\nclass ReuseProducer')
    end=src.index('class RowMaxConsumer',start);s=src[start:end].rstrip()
    s=s.replace('ReuseProducer','ResidentAProducer')
    s=once(s,'int32_t seq=0;bool cPending=false;','int32_t seq=0;bool cPending=false,aPending=false;\n    AscendC::TEventID aReady,aFree;')
    a=s.index('    __aicore__ inline void LoadStage(');z=s.index('        AscendC::Nd2NzParams qb{};',a)
    s=s[:a]+'''    __aicore__ inline void LoadA(int batch,int m0,int ar){
        if(aPending){AscendC::WaitFlag<AscendC::HardEvent::MTE1_MTE2>(aFree);aPending=false;}
        AscendC::Nd2NzParams q{};q.ndNum=1;
        q.nValue=TA?p.K:ar;q.dValue=TA?ar:p.K;
        q.srcDValue=TA?p.M:p.K;q.dstNzC0Stride=TA?p.K:ar;q.dstNzNStride=1;
        const int64_t off=int64_t(batch)*p.M*p.K+(TA?m0:int64_t(m0)*p.K);
        AscendC::DataCopy(a1Buf.template Get<T>(),a[off],q);
        AscendC::SetFlag<AscendC::HardEvent::MTE2_MTE1>(aReady);
        AscendC::WaitFlag<AscendC::HardEvent::MTE2_MTE1>(aReady);
    }
    __aicore__ inline void LoadStage(int batch,int m0,int n0,int ar,int br,int k0,int kr,int s){
        auto bb=b1Buf.template Get<T>()[s*K1*BN];
'''+s[z:]
    s=once(s,'int kr1,int kk,int kr0,int s1,int s0)','int kr1,int kk,int kr0,int s1,int s0,int kBase)')
    s=once(s,'auto sa=a1Buf.template Get<T>()[s1*AM*K1];','auto sa=a1Buf.template Get<T>();')
    s=once(s,'const int off=TA?(mo/16+i)*kr1*16+kk*16:(kk/16)*ar*16+(mo+i*16)*16;',
        'const int ak=kBase+kk;\n                const int off=TA?(mo/16+i)*p.K*16+ak*16:(ak/16)*ar*16+(mo+i*16)*16;')
    s=once(s,'LoadL0(ar,br,kr1,kk,kr0,s1,s0);','LoadL0(ar,br,kr1,kk,kr0,s1,s0,kBase);')
    s=s.replace('// Free L1 only after the last K0 slice has read BOTH shared operands.','// Release this B stage after its final L0 read; A remains resident across N macros.')
    s=once(s,'cReady=pipe->AllocEventID<AscendC::HardEvent::M_FIX>();',
        'aReady=pipe->AllocEventID<AscendC::HardEvent::MTE2_MTE1>();\n        aFree=pipe->AllocEventID<AscendC::HardEvent::MTE1_MTE2>();\n        cReady=pipe->AllocEventID<AscendC::HardEvent::M_FIX>();')
    s=once(s,'pipe->InitBuffer(a1Buf,2*AM*K1*sizeof(T));','pipe->InitBuffer(a1Buf,AM*p.K*sizeof(T));')
    s=once(s,'''            for(int m0=mBegin;m0<mEnd;m0+=AM)for(int n0=nBegin;n0<nEnd;n0+=BN)
                Macro(group,batch,m0,n0,MinI(AM,mEnd-m0),MinI(BN,nEnd-n0));''',
'''            for(int m0=mBegin;m0<mEnd;m0+=AM){
                const int ar=MinI(AM,mEnd-m0);LoadA(batch,m0,ar);
                for(int n0=nBegin;n0<nEnd;n0+=BN)Macro(group,batch,m0,n0,ar,MinI(BN,nEnd-n0));
                AscendC::SetFlag<AscendC::HardEvent::MTE1_MTE2>(aFree);aPending=true;
            }''')
    s=once(s,'        pipe_->ReleaseEventID<AscendC::HardEvent::M_FIX>(cReady);',
'''        if(aPending)AscendC::WaitFlag<AscendC::HardEvent::MTE1_MTE2>(aFree);
        pipe_->ReleaseEventID<AscendC::HardEvent::MTE2_MTE1>(aReady);
        pipe_->ReleaseEventID<AscendC::HardEvent::MTE1_MTE2>(aFree);
        pipe_->ReleaseEventID<AscendC::HardEvent::M_FIX>(cReady);''')
    return s+'\n'
def module2(src):
    s='''// BMMS1202_BEGIN
namespace bmms1202 {
using Plan=bmms11r2::Plan;using bmms83::MinI;
constexpr int TM=64,TN=128,AM=128,BN=256,K1=128,K0=64,MACRO_ELEMS=4*TM*TN;
constexpr uint16_t READY=4,FREE=6;
static inline bool Eligible(int B,int M,int N,int K,int cores){
    return B==1&&M>=1024&&N>=1024&&K>=1024&&K<1536&&bmms11r2::Eligible(B,M,N,K,cores);
}
static inline Plan MakePlan(int B,int M,int N,int K,int cores){return bmms11r2::MakePlan(B,M,N,K,cores);}
static inline bool ReusesA(const Plan& p){return p.nTiles/p.pN>=2;}
'''+producer(src)+'''} // namespace bmms1202
// BMMS1202_CPU_END
namespace bmms1202 {
template<class T,bool TA,bool TB>
__aicore__ inline void Entry(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ring,GM_ADDR part,Plan p){
    AscendC::TPipe pipe;
    if ASCEND_IS_AIC {ResidentAProducer<T,TA,TB> op;op.Init(a,b,ring,p,&pipe);op.Process();}
    if ASCEND_IS_AIV {bmms11r2::RowMaxConsumer op;op.Init(ring,part,y,p,&pipe);op.Process();}
}
}
#define BMMS1202_KERNEL(NAME,T,TA,TB) \\
__schedmode__(1) __global__ __mix__(1,2) void NAME(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ring,GM_ADDR part,bmms1202::Plan p){bmms1202::Entry<T,TA,TB>(a,b,y,ring,part,p);}
'''
    for dt,T in [('f16','half'),('b16','bfloat16_t')]:
        for suf,ta,tb in [('nn','false','false'),('nt','false','true'),('tn','true','false'),('tt','true','true')]:s+=f'BMMS1202_KERNEL(bmms1202_{dt}_{suf},{T},{ta},{tb})\n'
    h=host(src,'bmms11r2').replace('BMMS11R2_LAUNCH','BMMS1202_LAUNCH').replace('bmms11r2_f16','bmms1202_f16').replace('bmms11r2_b16','bmms1202_b16')
    h=once(h,'const auto p=MakePlan(B,M,N,K,cores);uint8_t* ws=nullptr;','const auto p=MakePlan(B,M,N,K,cores);if(!ReusesA(p))return false;uint8_t* ws=nullptr;')
    h=h.replace('WorkspaceBytes(p)','bmms11r2::WorkspaceBytes(p)').replace('ws+RingBytes(p)','ws+bmms11r2::RingBytes(p)')
    return s+'#undef BMMS1202_KERNEL\nnamespace bmms1202 {\n'+h+'\n}\n// BMMS1202_END\n\n'
def module3(src):
    dev=function(src,'template<class T,bool TA,bool TB>\n__aicore__ inline void Device(GM_ADDR a,GM_ADDR b,GM_ADDR y,const Plan& p)')
    dev=once(dev,'template<class T,bool TA,bool TB>','template<class T,bool TA,bool TB,int K>')
    dev=once(dev,'const int M=p.M,N=p.N,K=p.K,kp=p.kp,D=M*N,nr=(N+7)/8*8;',
        'constexpr int kp=K<=32?32:K<=64?64:128;\n    constexpr bool DIRECT_A=!TA&&K==kp,DIRECT_B=TB&&K==kp;\n    const int M=p.M,N=p.N,D=M*N,nr=(N+7)/8*8;')
    dev=once(dev,'pipe.InitBuffer(packed,(M+N)*kp*4);','pipe.InitBuffer(packed,((DIRECT_A?0:M)+(DIRECT_B?0:N))*kp*4+32);')
    dev=once(dev,'auto bp=packed.Get<float>(),ap=bp[N*kp],prod=products.Get<float>();',
        'auto pack=packed.Get<float>();\n    auto bp=DIRECT_B?fb:pack,ap=DIRECT_A?fa:pack[(DIRECT_B?0:N)*kp],prod=products.Get<float>();')
    dev=once(dev,'''    AscendC::CreateVecIndex(ia,int32_t(0),K);AscendC::CreateVecIndex(ib,int32_t(0),K);
    AscendC::PipeBarrier<PIPE_V>();
    AscendC::Muls(ia,ia,int32_t((TA?M:1)*4),K);AscendC::Muls(ib,ib,int32_t((TB?1:N)*4),K);''',
'''    if constexpr(!DIRECT_A)AscendC::CreateVecIndex(ia,int32_t(0),K);
    if constexpr(!DIRECT_B)AscendC::CreateVecIndex(ib,int32_t(0),K);
    AscendC::PipeBarrier<PIPE_V>();
    if constexpr(!DIRECT_A)AscendC::Muls(ia,ia,int32_t((TA?M:1)*4),K);
    if constexpr(!DIRECT_B)AscendC::Muls(ib,ib,int32_t((TB?1:N)*4),K);''')
    dev=once(dev,'AscendC::Duplicate(bp,0.0f,(M+N)*kp);AscendC::Duplicate(rows,0.0f,M*8);',
'''if constexpr(!DIRECT_B)AscendC::Duplicate(bp,0.0f,N*kp);
    if constexpr(!DIRECT_A)AscendC::Duplicate(ap,0.0f,M*kp);
    AscendC::Duplicate(rows,0.0f,M*8);''')
    dev=once(dev,'for(int n=0;n<N;++n)AscendC::Gather','if constexpr(!DIRECT_B)for(int n=0;n<N;++n)AscendC::Gather')
    dev=once(dev,'for(int m=0;m<M;++m)AscendC::Gather','if constexpr(!DIRECT_A)for(int m=0;m<M;++m)AscendC::Gather')
    s='''// BMMS1203_BEGIN
namespace bmms1203 {
using Plan=bmms50::Plan;
static inline bool Eligible(int B,int M,int N,int K){return bmms50::Eligible(B,M,N,K);}
static inline Plan MakePlan(int M,int N,int K){return bmms50::MakePlan(M,N,K);}
'''+dev+'''
} // namespace bmms1203
// BMMS1203_CPU_END
#define BMMS1203_KERNEL(NAME,T,TA,TB,K) \\
__global__ __aicore__ void NAME(GM_ADDR a,GM_ADDR b,GM_ADDR y,bmms1203::Plan p){bmms1203::Device<T,TA,TB,K>(a,b,y,p);}
'''
    for K in range(32,129,8):
        for dt,T in [('f16','half'),('b16','bfloat16_t')]:
            for suf,ta,tb in [('nn','false','false'),('nt','false','true'),('tn','true','false'),('tt','true','true')]:s+=f'BMMS1203_KERNEL(bmms1203_{dt}_{suf}_{K},{T},{ta},{tb},{K})\n'
    s+='''#undef BMMS1203_KERNEL
namespace bmms1203 {
static inline bool TryLaunch(GM_ADDR a,GM_ADDR b,GM_ADDR y,int B,int M,int N,int K,int dtype,bool ta,bool tb,aclrtStream stream){
    if((dtype!=1&&dtype!=2)||!Eligible(B,M,N,K))return false;
    const auto p=MakePlan(M,N,K);
#define BMMS1203_LAUNCH(NAME) NAME<<<1,nullptr,stream>>>(a,b,y,p)
'''
    for i,dt in enumerate(['f16','b16']):
        s+=('    if(dtype==1){\n' if i==0 else '    }else{\n')
        for j,(suf,cond) in enumerate([('nn','!ta&&!tb'),('nt','!ta&&tb'),('tn','ta&&!tb'),('tt','')]):
            s+=('        if' if j==0 else '        else if' if j<3 else '        else')+(f'({cond})' if cond else '')+'{switch(K){\n'
            for K in range(32,129,8):s+=f'            case {K}:BMMS1203_LAUNCH(bmms1203_{dt}_{suf}_{K});return true;\n'
            s+='        }}\n'
    return s+'''    }
#undef BMMS1203_LAUNCH
    return false;
}
}
// BMMS1203_END

'''
def main():
    raw=BASE.read_bytes();assert hashlib.sha256(raw).hexdigest()==SHA;src=raw.decode().replace('\r\n','\n');OUT.mkdir(exist_ok=True)
    records=[]
    for r,mod in [(2,module2(src)),(3,module3(src))]:
        fragment=mod.encode();anchor=b'extern "C" void run_kernel(GM_ADDR a,const TensorGroupInfo& ia,'
        marker=(b'    if(bmms11r2::TryLaunch' if r==2 else b'    if(bmms50::TryLaunch')
        start=raw.index(marker);end=raw.index(b'\n',start)+1;line=raw[start:end]
        call=('bmms1202::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream)' if r==2 else 'bmms1203::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,stream)')
        hook=('    if('+call+')return;\r\n').encode();data=raw.replace(anchor,fragment+anchor,1).replace(line,hook+line,1)
        assert data.replace(fragment,b'',1).replace(hook,b'',1)==raw
        (OUT/(NAMES[r]+'.asc')).write_bytes(data);write(H/f'r0{r}_extracted.hpp',between(mod,f'// BMMS120{r}_BEGIN',f'// BMMS120{r}_CPU_END'))
        records.append({'candidate':NAMES[r]+'.asc','sha256':hashlib.sha256(data).hexdigest(),'parent_sha256':SHA,'parent_recovered_byte_for_byte':True,'independent_from_other_candidate':True})
    write(OUT/'v12_r02_r03_manifest.json',json.dumps(records,indent=2)+'\n');print(json.dumps(records,indent=2))
if __name__=='__main__':main()

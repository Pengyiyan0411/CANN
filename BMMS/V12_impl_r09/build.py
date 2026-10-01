"""r09: retain one full narrow B panel in L0B across Native M tiles."""
from pathlib import Path
import hashlib
import importlib.util
import json

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'BMMS_V12';BASE=OUT/'v12_baseline_r03.asc'
SHA='1c9e9726aa43fdd177c98c645c69bb7d57721d2f1b07d00dfb614324286a404c'
spec=importlib.util.spec_from_file_location('helpers',ROOT/'V12_impl_r02_r03/build.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)


def module(src):
    a=src.index('template<class T,bool TA,bool TB,int TK>\nclass SmallKProducer')
    z=src.index('class SmallKConsumer',a)
    producer=src[a:z].strip().replace('SmallKProducer','ResidentBProducer')
    producer=producer.replace('auto dstB=b2Buf.template Get<T>()[slot*TK*TN];',
                              'auto dstB=b2Buf.template Get<T>();')
    a=producer.index('        AscendC::LoadData2DParams lb{};')
    z=producer.index('        AscendC::SetFlag<AscendC::HardEvent::MTE1_M>',a)
    producer=producer[:a]+'''        // B=1, pN=1, N<=64 and one task per group guarantee this
        // complete B operand is invariant for every M tile. L0B is never
        // overwritten after its first fill; the original first-tile event
        // still establishes MTE1 -> M visibility.
        if(seq==0){
'''+producer[a:z]+'''        }
'''+producer[z:]
    producer=producer.replace('auto bb=b2Buf.template Get<T>()[slot*TK*TN];',
                              'auto bb=b2Buf.template Get<T>();')
    producer=producer.replace('pipe->InitBuffer(b2Buf,2*TK*TN*sizeof(T));',
                              'pipe->InitBuffer(b2Buf,TK*TN*sizeof(T));')
    s='''// BMMS1209_BEGIN
// Independent of r07/r08: original Native consumer and sum order retained.
namespace bmms1209 {
using NativePlan=bmms83::NativePlan;
using Plan=NativePlan;
using bmms83::MinI;
constexpr int TM=bmms83::TM,TN=bmms83::TN,AM=bmms83::AM,BN=bmms83::BN;
constexpr int PACKET_TILES=bmms83::PACKET_TILES;
constexpr uint16_t READY=bmms83::READY,FREE=bmms83::FREE;
static inline bool Select(const Plan& p){
    return bmms49::Select(p)&&p.tasks==p.blocks&&p.mTiles>p.pM;
}
'''+producer+'''
template<class T,bool TA,bool TB>
__aicore__ inline void Entry(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ring,GM_ADDR partial,Plan p){
    AscendC::TPipe pipe;
    if ASCEND_IS_AIC {ResidentBProducer<T,TA,TB,128> op;op.Init(a,b,ring,p,&pipe);op.Process();}
    if ASCEND_IS_AIV {bmms49::NarrowPacketConsumer op;op.Init(ring,partial,y,p,&pipe);op.Process();}
}
}
#define BMMS1209_KERNEL(NAME,T,TA,TB) \\
__schedmode__(1) __global__ __mix__(1,2) void NAME(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ring,GM_ADDR part,bmms1209::Plan p){bmms1209::Entry<T,TA,TB>(a,b,y,ring,part,p);}
'''
    for dt,T in [('f16','half'),('b16','bfloat16_t')]:
        for suffix,ta,tb in [('nn','false','false'),('nt','false','true'),('tn','true','false'),('tt','true','true')]:
            s+=f'BMMS1209_KERNEL(bmms1209_{dt}_{suffix},{T},{ta},{tb})\n'
    host=h.host(src,'bmms49').replace('BMMS49','BMMS1209').replace('bmms49','bmms1209')
    return s+'#undef BMMS1209_KERNEL\nnamespace bmms1209 {\n'+host+'\n}\n// BMMS1209_END\n\n'


def main():
    raw=BASE.read_bytes();assert hashlib.sha256(raw).hexdigest()==SHA
    fragment=module(raw.decode().replace('\r\n','\n')).encode()
    anchor=b'extern "C" void run_kernel(GM_ADDR a,const TensorGroupInfo& ia,'
    marker=b'        if(bmms49::TryLaunch(a,b,y,p,x.dtype,ta,tb,stream))return;'
    hook=b'        if(bmms1209::TryLaunch(a,b,y,p,x.dtype,ta,tb,stream))return;\r\n'
    assert raw.count(marker)==1
    data=raw.replace(anchor,fragment+anchor,1).replace(marker,hook+marker,1)
    assert data.replace(fragment,b'',1).replace(hook,b'',1)==raw
    target=OUT/'v12_r09_native_b_l0_resident.asc';target.write_bytes(data)
    (ROOT/'V12_npu_lab/harness/r09.asc').write_bytes(data)
    event=(ROOT/'V12_npu_lab/harness/event_bench.asc').read_text()
    event=event.replace('DISPATCH(bmms1207)','DISPATCH(bmms1209)').replace('DISPATCH(bmms11r2)','DISPATCH(bmms49)')
    event=event.replace('bmms1207::Eligible(B,M,N,K,cores)',
                        '(bmms83::NativeEligible(M,N,K)&&bmms1209::Select(bmms83::MakeNative(B,M,N,K,cores)))')
    event=event.replace('bmms11r2::MakePlan(B,M,N,K,cores)','bmms83::MakeNative(B,M,N,K,cores)')
    event=event.replace('bmms11r2::RingBytes(p)','bmms83::NativeRingBytes(p)')
    event=event.replace('bmms11r2::WorkspaceBytes(p)','(bmms83::NativeRingBytes(p)+bmms83::NativePartialBytes(p))')
    event=event.replace('candidate?"r07"','candidate?"r09"')
    (ROOT/'V12_npu_lab/harness/event_bench_r09.asc').write_text(event)
    report=dict(candidate=target.name,sha256=hashlib.sha256(data).hexdigest(),parent=BASE.name,
                parent_sha256=SHA,parent_recovered_byte_for_byte=True,
                consumer_grid_workspace_sum_order_unchanged=True,
                b_l0_bytes_allocated=128*128*2,b_l0_fill_count_per_group=1,
                scope='Metadata/lifetime review; actual device validation pending.')
    (OUT/'v12_r09_manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()

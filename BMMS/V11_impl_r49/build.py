"""R49 = byte-preserved R48 + a consumer-only narrow-N experiment."""
from pathlib import Path
import hashlib,json,importlib.util
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;OUT=ROOT/'BMMS_V11_R49'
BASE=ROOT/'BMMS_V11_R47_R48/R48_RESIDUAL_BATCH_OWNER.asc'
R43=ROOT/'V11_analysis_r43/R43_CASE8_PADDED_MACRO.asc'
SHA='7f48ea4ec9346a7cd61745394a8578e97e5c834b126a981982e8bc0f82a87d72'
NAME='R49_NATIVE_CONSUMER_ONLY'
spec=importlib.util.spec_from_file_location('r49_helpers',ROOT/'V11_impl_r47_r48/build.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
write,once,between,function,host=old.write,old.once,old.between,old.function,old.host
def module():
    prefix='''// BMMS49_BEGIN
namespace bmms49 {
using Plan=bmms83::NativePlan;
using bmms83::MinI;
constexpr int32_t TM=bmms83::TM,TN=bmms83::TN,AM=bmms83::AM,PACKET_TILES=bmms83::PACKET_TILES;
constexpr uint16_t READY=bmms83::READY,FREE=bmms83::FREE;
static inline bool Select(const Plan& p){
    return p.B==1&&p.K==128&&p.M>256&&p.M<=8192&&p.M%16==0&&
        (p.N==48||p.N==64)&&p.pN==1&&p.blocks>1;
}
'''
    s=prefix+(HERE/'consumer.inc').read_text(encoding='utf-8')
    s+=old.bindings(49,'bmms83::SmallKProducer<T,TA,TB,128>','NarrowPacketConsumer')
    h=host(BASE.read_text(encoding='utf-8'),'bmms25')
    # R25's launcher dispatches two consumer families; construct the narrow-only
    # launch from the already compiled R03 wrapper instead.
    h=host(BASE.read_text(encoding='utf-8'),'bmms11d')
    start=h.index('    uint8_t* ws=nullptr;')
    h='''static inline bool TryLaunch(GM_ADDR a,GM_ADDR b,GM_ADDR y,const Plan& p,
    int32_t dtype,bool ta,bool tb,aclrtStream stream){
    if((dtype!=1&&dtype!=2)||!Select(p))return false;
'''+h[start:]
    h=h.replace('WorkspaceBytes(p)','bmms83::NativeRingBytes(p)+bmms83::NativePartialBytes(p)').replace('ws+RingBytes(p)','ws+bmms83::NativeRingBytes(p)')
    h=h.replace('BMMS11D_LAUNCH','BMMS49_LAUNCH').replace('bmms11d_f16','bmms49_f16').replace('bmms11d_b16','bmms49_b16')
    return s+h+'\n} // namespace bmms49\n// BMMS49_END\n\n'
def main():
    raw=BASE.read_bytes();assert hashlib.sha256(raw).hexdigest()==SHA
    assert hashlib.sha256(R43.read_bytes()).hexdigest()==old.SHA
    OUT.mkdir(exist_ok=True)
    frag=module().encode();anchor=b'extern "C" void run_kernel(GM_ADDR a,const TensorGroupInfo& ia,'
    assert raw.count(anchor)==1
    data=raw.replace(anchor,frag+anchor,1)
    mark=b'        if(bmms25::TryLaunch(a,b,y,p,x.dtype,ta,tb,stream))return;'
    hook=b'        if(bmms49::TryLaunch(a,b,y,p,x.dtype,ta,tb,stream))return;\r\n'
    assert data.count(mark)==1;data=data.replace(mark,hook+mark,1)
    assert data.replace(frag,b'',1).replace(hook,b'',1)==raw
    (OUT/(NAME+'.asc')).write_bytes(data)
    write(HERE/'r49_extracted.hpp',between(module(),'// BMMS49_BEGIN','// BMMS49_CPU_END'))
    report={'candidate':NAME+'.asc','sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),
            'parent_R48_sha256':SHA,'frozen_R43_sha256':old.SHA,'R48_recovered_byte_for_byte':True,
            'new_producer':'none; calls original bmms83::SmallKProducer<T,TA,TB,128>',
            'new_planner':'none; consumes unchanged run_kernel NativePlan',
            'packet_tiles':4,'ring_layout':'original TM64/TN128',
            'new_scope':'Native B1 K128 M>256 N48/64 consumer only',
            'preserved_R48_case7':True}
    write(OUT/'MANIFEST.json',json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()

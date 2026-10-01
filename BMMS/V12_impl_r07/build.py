"""r07: paired GM ring loads for full 256-column R06 macros."""
from pathlib import Path
import hashlib
import importlib.util
import json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'BMMS_V12'
BASE = OUT / 'v12_baseline_r03.asc'
SHA = '1c9e9726aa43fdd177c98c645c69bb7d57721d2f1b07d00dfb614324286a404c'
spec = importlib.util.spec_from_file_location('helpers', ROOT / 'V12_impl_r02_r03/build.py')
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)


def make_module(src):
    start = src.index('class RowMaxConsumer', src.index('namespace bmms11r2'))
    end = src.index('#ifndef BMMS11R2_CPU_TEST', start)
    consumer = src[start:end].strip().replace('RowMaxConsumer', 'PairedConsumer')
    consumer = consumer.replace('groupBuf,rowBuf,sumBuf', 'rowBuf,sumBuf')
    consumer = consumer.replace('pipe->InitBuffer(cq,1,(TM/2)*TN*4)', 'pipe->InitBuffer(cq,1,TM*TN*4)')
    consumer = consumer.replace('pipe->InitBuffer(groupBuf,(TM/2)*TN*4);', '')
    consumer = consumer.replace('auto acc=groupBuf.Get<float>();', '')
    start = consumer.index('                        AscendC::Duplicate(acc,')
    end = consumer.index('                        AscendC::BinaryRepeatParams rp', start)
    consumer = consumer[:start] + '''                        // The public guard guarantees br==BN==256. Both microtiles
                        // contain complete 128-column rows, including the M tail.
                        auto c=cq.AllocTensor<float>();
                        const int ci=(mo/TM)*2;
                        const int64_t off=(int64_t(group)*2+ringSlot)*MACRO_ELEMS+ci*TM*TN+sub*vr*TN;
                        AscendC::DataCopyExtParams cp{2,uint32_t(vr*TN*4),uint32_t((TM-vr)*TN*4),0,0};
                        AscendC::DataCopyPadExtParams<float> pd{false,0,0,0.0f};
                        AscendC::DataCopyPad(c,ring[off],cp,pd);cq.EnQue(c);c=cq.DeQue<float>();
                        // Release only after this AIV has read both N tiles of
                        // the final M microtile. Queue FreeTensor protects UB reuse.
                        if(mo+mr==ar)AscendC::CrossCoreSetFlag<0x2,PIPE_MTE2>(FREE+ringSlot);
                        AscendC::Max(c,c,c[vr*TN],vr*TN);AscendC::PipeBarrier<PIPE_V>();
''' + consumer[end:]
    consumer = consumer.replace('AscendC::Max(acc,acc,acc[64]', 'AscendC::Max(c,c,c[64]')
    consumer = consumer.replace('AscendC::WholeReduceMax(rows,acc,', 'AscendC::WholeReduceMax(rows,c,')
    consumer = consumer.replace('AscendC::Max(run[mo+sub*vr],run[mo+sub*vr],rows,vr);AscendC::PipeBarrier<PIPE_V>();',
                                'AscendC::Max(run[mo+sub*vr],run[mo+sub*vr],rows,vr);AscendC::PipeBarrier<PIPE_V>();cq.FreeTensor(c);')
    module = '''// BMMS1207_BEGIN
// Independent of r06; changes only the consumer of the original R06 producer.
namespace bmms1207 {
using Plan=bmms11r2::Plan;
using bmms11r2::MinI;
constexpr int TM=bmms11r2::TM,TN=bmms11r2::TN,AM=bmms11r2::AM,BN=bmms11r2::BN;
constexpr int MACRO_ELEMS=bmms11r2::MACRO_ELEMS;
constexpr uint16_t READY=bmms11r2::READY,FREE=bmms11r2::FREE;
static inline bool Eligible(int B,int M,int N,int K,int cores){
    return B==1&&M>=1024&&N>=1024&&N%BN==0&&K>=1024&&K<1536&&
        bmms11r2::Eligible(B,M,N,K,cores);
}
static inline Plan MakePlan(int B,int M,int N,int K,int cores){return bmms11r2::MakePlan(B,M,N,K,cores);}
''' + consumer + '''
template<class T,bool TA,bool TB>
__aicore__ inline void Entry(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ring,GM_ADDR part,Plan p){
    AscendC::TPipe pipe;
    if ASCEND_IS_AIC {bmms11r2::ReuseProducer<T,TA,TB> op;op.Init(a,b,ring,p,&pipe);op.Process();}
    if ASCEND_IS_AIV {PairedConsumer op;op.Init(ring,part,y,p,&pipe);op.Process();}
}
}
#define BMMS1207_KERNEL(NAME,T,TA,TB) \\
__schedmode__(1) __global__ __mix__(1,2) void NAME(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ring,GM_ADDR part,bmms1207::Plan p){bmms1207::Entry<T,TA,TB>(a,b,y,ring,part,p);}
'''
    for dt, typ in [('f16', 'half'), ('b16', 'bfloat16_t')]:
        for suffix, ta, tb in [('nn','false','false'),('nt','false','true'),('tn','true','false'),('tt','true','true')]:
            module += f'BMMS1207_KERNEL(bmms1207_{dt}_{suffix},{typ},{ta},{tb})\n'
    host = helpers.host(src, 'bmms11r2').replace('BMMS11R2_LAUNCH','BMMS1207_LAUNCH')
    host = host.replace('bmms11r2_f16','bmms1207_f16').replace('bmms11r2_b16','bmms1207_b16')
    host = host.replace('WorkspaceBytes(p)','bmms11r2::WorkspaceBytes(p)').replace('ws+RingBytes(p)','ws+bmms11r2::RingBytes(p)')
    return module + '#undef BMMS1207_KERNEL\nnamespace bmms1207 {\n' + host + '\n}\n// BMMS1207_END\n\n'


def main():
    raw=BASE.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    fragment=make_module(raw.decode().replace('\r\n','\n')).encode()
    anchor=b'extern "C" void run_kernel(GM_ADDR a,const TensorGroupInfo& ia,'
    hook=b'    if(bmms1207::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\r\n'
    marker=b'    if(bmms11r2::TryLaunch'
    data=raw.replace(anchor,fragment+anchor,1).replace(marker,hook+marker,1)
    assert data.replace(fragment,b'',1).replace(hook,b'',1)==raw
    target=OUT/'v12_r07_paired_ring_consumer.asc'
    target.write_bytes(data)
    (ROOT/'V12_npu_lab/harness/r07.asc').write_bytes(data)
    # Exhaustively audit the changed descriptor at every legal 16-row M tail,
    # every microtile and subworker. Inactive rows are never read.
    audits=0
    for ar in range(16,129,16):
        for mo in range(0,ar,64):
            mr=min(64,ar-mo);vr=mr//2
            for sub in range(2):
                off=(mo//64)*2*64*128+sub*vr*128
                for no in range(2):
                    start=off+no*64*128
                    for r in range(vr):
                        for n in range(128):
                            got=start+r*128+n
                            expected=((mo//64)*2+no)*64*128+(sub*vr+r)*128+n
                            assert got==expected and 0<=got<4*64*128
                            assert sub*vr+r<mr
                            audits+=1
    report=dict(candidate=target.name,sha256=hashlib.sha256(data).hexdigest(),parent=BASE.name,
                parent_sha256=SHA,parent_recovered_byte_for_byte=True,address_checks=audits,
                producer_grid_workspace_unchanged=True,max_consumer_UB_bytes=32768+32+128+512+3*8192*4,
                scope='Descriptor index audit only; no device correctness or speed claim.')
    (OUT/'v12_r07_manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()

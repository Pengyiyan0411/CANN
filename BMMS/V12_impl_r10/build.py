"""Case15 candidate: load an entire K shard into L1, maximize bounded L0 K."""
from pathlib import Path
import hashlib, json

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'BMMS_V12/v12_baseline_r03.asc'
SHA='1c9e9726aa43fdd177c98c645c69bb7d57721d2f1b07d00dfb614324286a404c'

def module(src):
    start=src.index('namespace bmms23 {')
    end=src.index('// Each batch has one AIV owner:',start)
    consumer=src[end:src.index('#ifndef BMMS23_CPU_TEST',end)]
    producer=(Path(__file__).parent/'producer.asc').read_text()
    s='''// BMMS1210_BEGIN
// Same Split-K plan and merge tree; whole-shard L1, capacity-bounded L0.
namespace bmms1210 {
using Plan=bmms23::Plan;
constexpr int TM=bmms23::TM,TN=bmms23::TN,ROWS=bmms23::ROWS;
constexpr uint16_t READY=bmms23::READY;
static inline bool Eligible(int B,int M,int N,int K,int dtype,int cores){
    return bmms23::Eligible(B,M,N,K,dtype,cores)&&B==1&&M<=64&&N<=128&&M*N<=4096
        &&bmms23::MakePlan(B,M,N,K,cores).splits>=8;
}
'''+producer+consumer+'''
template<class T,bool TA,bool TB>
__aicore__ inline void Entry(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ws,Plan p){
    AscendC::TPipe pipe;
    if ASCEND_IS_AIC {Producer<T,TA,TB> op;op.Init(a,b,ws,p,&pipe);op.Process();}
    if ASCEND_IS_AIV {Consumer op;op.Init(ws,y,p,&pipe);op.Process();}
}
}
#define BMMS1210_KERNEL(NAME,T,TA,TB) \\
__schedmode__(1) __global__ __mix__(1,2) void NAME(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ws,bmms1210::Plan p){bmms1210::Entry<T,TA,TB>(a,b,y,ws,p);}
'''
    for dt,T in [('f16','half'),('b16','bfloat16_t')]:
        for layout,ta,tb in [('nn','false','false'),('nt','false','true'),('tn','true','false'),('tt','true','true')]:
            s+=f'BMMS1210_KERNEL(bmms1210_{dt}_{layout},{T},{ta},{tb})\n'
    a=src.index('static inline bool TryLaunch(',src.index('#undef BMMS23_KERNEL'))
    z=src.index('} // namespace bmms23',a)
    host=src[a:z].replace('Plan p=MakePlan(', 'Plan p=bmms23::MakePlan(')
    host=host.replace('    if(BMMS23_SINGLE_K_CONTROL){p.splits=1;p.blocks=B*p.mTiles*p.nTiles;}\n','')
    host=host.replace('WorkspaceBytes(p)','bmms23::WorkspaceBytes(p)').replace('BMMS23','BMMS1210').replace('bmms23_f16','bmms1210_f16').replace('bmms23_b16','bmms1210_b16')
    return s+'#undef BMMS1210_KERNEL\nnamespace bmms1210 {\n'+host+'}\n// BMMS1210_END\n\n'

def main():
    raw=BASE.read_bytes();assert hashlib.sha256(raw).hexdigest()==SHA
    fragment=module(raw.decode().replace('\r\n','\n')).encode()
    anchor=b'extern "C" void run_kernel(GM_ADDR a,const TensorGroupInfo& ia,'
    marker=b'    if(bmms23::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;'
    hook=marker.replace(b'bmms23::',b'bmms1210::')+b'\r\n'
    assert raw.count(marker)==1 and raw.count(anchor)==1
    data=raw.replace(anchor,fragment+anchor,1).replace(marker,hook+marker,1)
    assert data.replace(fragment,b'',1).replace(hook,b'',1)==raw
    target=ROOT/'BMMS_V12/v12_r10_splitk_full_shard.asc';target.write_bytes(data)
    (ROOT/'V12_npu_lab/harness/r10.asc').write_bytes(data)
    report=dict(candidate=target.name,sha256=hashlib.sha256(data).hexdigest(),parent=BASE.name,parent_sha256=SHA,
                parent_recovered_byte_for_byte=True,split_count_workspace_consumer_unchanged=True,
                scope='B1 M<=64 N<=128 MN<=4096 original Split-K S>=8; device validation pending')
    (ROOT/'BMMS_V12/v12_r10_manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    state=ROOT/'BMMS_V12/MAINLINE.json';doc=json.loads(state.read_text())
    for c in doc['candidates']:
        if c['version']=='v12_r07':c['status']='user reports actual Judge benefit drowned by noise; not promoted; synthetic evidence retained for reference'
    doc['naming']='v12_rxx; r03 accepted; r06-r09 not promoted; r10 targets Case15'
    doc['next_action']='Keep r03 frozen; validate Case15 whole-shard producer r10 on NPU; no inherited r07/r08/r09 changes.'
    state.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()

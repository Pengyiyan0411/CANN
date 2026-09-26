"""R22: host shape switch -> independent, statically sized device entry points."""
from pathlib import Path
import hashlib,json,difflib,shutil
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;OUT=ROOT/'BMMS_V11_R22'
BASE=ROOT/'BMMS_V11_R13_R14/R14_FLEX_SINGLE_WAVE.asc'
BASE_SHA='64eb6eeeb10d2418845d2026b9e9fdd2088d0a3ad1decb0a1bfc46d65cfa78fe'
NAME='R22_SHAPE_SWITCH'
CONFIGS={'sn':(64,32,256,32,[32,64,128]),'sm':(32,256,32,512,[32,64]),'dn':(128,128,256,512,[32,64,128])}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,s):p.write_text(s,encoding='utf-8',newline='\n')
def once(s,a,b):
    assert s.count(a)==1,(s.count(a),a[:100]);return s.replace(a,b,1)
def between(s,a,b):
    i=s.index(a);return s[i:s.index(b,i)]

PARAMS='int TM,int TN,int AM,int BN'
def producer(original):
    s=between(original,'template<class T,bool TA,bool TB,int TK>\nclass SmallKProducer {','class SmallKConsumer {')
    s=once(s,'template<class T,bool TA,bool TB,int TK>\nclass SmallKProducer {',
        'template<class T,bool TA,bool TB,int TK,'+PARAMS+'>\nclass Producer {\n'+'''
    static_assert(TK==32||TK==64||TK==128,"fixed small K only");
    static_assert(TM%16==0&&TN%16==0&&AM%TM==0&&BN%TN==0,"aligned tile geometry");
    static_assert(2*TM*TK*sizeof(T)<=64*1024,"L0A capacity");
    static_assert(2*TN*TK*sizeof(T)<=64*1024,"L0B capacity");
    static_assert(2*TM*TN*sizeof(float)<=128*1024,"L0C capacity");
    static_assert((AM+2*BN)*TK*sizeof(T)<=512*1024,"L1 capacity");
''')
    s=s.replace('NativePlan','Plan')
    return s

def consumer(original):
    s=between(original,'class SmallKPacketConsumer {','template<class T,bool TA,bool TB,int TK>\n__aicore__ inline void NativeEntry(')
    s=once(s,'class SmallKPacketConsumer {','template<'+PARAMS+'>\nclass Consumer {')
    s=s.replace('NativePlan','Plan')
    a='''                        AscendC::BinaryRepeatParams rp{1,1,1,16,16,16};
                        AscendC::Max(acc,acc,acc[64],64,vr,rp);AscendC::PipeBarrier<PIPE_V>();
                        AscendC::WholeReduceMax(rows,acc,64,vr,1,1,16,AscendC::ReduceOrder::ORDER_ONLY_VALUE);'''
    b='''                        // 32, 128 and 256-column rows use matching vector strides.
                        AscendC::BinaryRepeatParams rp{1,1,1,TN/8,TN/8,TN/8};
                        if constexpr(TN==256){
                            AscendC::Max(acc,acc,acc[128],64,vr,rp);
                            AscendC::Max(acc[64],acc[64],acc[192],64,vr,rp);
                            AscendC::PipeBarrier<PIPE_V>();
                        }
                        if constexpr(TN>=128){
                            AscendC::Max(acc,acc,acc[64],64,vr,rp);AscendC::PipeBarrier<PIPE_V>();
                        }
                        AscendC::WholeReduceMax(rows,acc,TN<64?TN:64,vr,1,1,TN/8,AscendC::ReduceOrder::ORDER_ONLY_VALUE);'''
    return once(s,a,b)

def kernels():
    s='''#ifndef BMMS22_CPU_TEST
template<class T,bool TA,bool TB,int TK,int TM,int TN,int AM,int BN>
__aicore__ inline void Entry(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ring,GM_ADDR partial,Plan p){
    AscendC::TPipe pipe;
    if ASCEND_IS_AIC {Producer<T,TA,TB,TK,TM,TN,AM,BN> op;op.Init(a,b,ring,p,&pipe);op.Process();}
    if ASCEND_IS_AIV {Consumer<TM,TN,AM,BN> op;op.Init(ring,partial,y,p,&pipe);op.Process();}
}
#endif
} // namespace bmms22
// BMMS22_CPU_EXTRACT_END

#define BMMS22_KERNEL(NAME,T,TA,TB,TK,TM,TN,AM,BN) \\
__schedmode__(1) __global__ __mix__(1,2) void NAME(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ring,GM_ADDR partial,bmms22::Plan p){bmms22::Entry<T,TA,TB,TK,TM,TN,AM,BN>(a,b,y,ring,partial,p);}
'''
    for tag,(tm,tn,am,bn,ks) in CONFIGS.items():
        for k in ks:
            for dt,t in [('f16','half'),('b16','bfloat16_t')]:
                for layout,ta,tb in [('nn','false','false'),('nt','false','true'),('tn','true','false'),('tt','true','true')]:
                    s+=f'BMMS22_KERNEL(bmms22_{tag}_{dt}_{layout}_k{k},{t},{ta},{tb},{k},{tm},{tn},{am},{bn})\n'
    return s+'#undef BMMS22_KERNEL\n'

def launch_family(tag,ks):
    s=''
    for i,k in enumerate(ks):
        s+=f'        {"if" if i==0 else "else if"}(K=={k}){{\n'
        s+='            if(dtype==1){\n'
        for di,dt in enumerate(['f16','b16']):
            if di:s+='            }else{\n'
            for li,(layout,ta,tb) in enumerate([('nn',False,False),('nt',False,True),('tn',True,False),('tt',True,True)]):
                cond=('if' if li==0 else 'else if')+'('+('ta' if ta else '!ta')+'&&'+('tb' if tb else '!tb')+')'
                s+=f'                {cond}{{BMMS22_LAUNCH(bmms22_{tag}_{dt}_{layout}_k{k});}}\n'
        s+='            }\n        }\n'
    return s

def host_launch():
    s='''namespace bmms22 {
static inline bool TryLaunch(GM_ADDR a,GM_ADDR b,GM_ADDR y,int B,int M,int N,int K,int dtype,bool ta,bool tb,int cores,aclrtStream stream){
    const Selection selection=Select(B,M,N,K,dtype,ta,tb,cores);
    if(selection.strategy==Strategy::R14)return false;
    const Plan p=selection.plan;const uint64_t rb=RingBytes(selection),pb=PartialBytes(p);
    uint8_t* ws=nullptr;
    if(aclrtMalloc(reinterpret_cast<void**>(&ws),rb+pb,ACL_MEM_MALLOC_HUGE_FIRST)!=ACL_SUCCESS)std::abort();
    uint8_t* partial=ws+rb;
#define BMMS22_LAUNCH(NAME) NAME<<<p.blocks,nullptr,stream>>>(a,b,y,ws,partial,p)
'''
    for i,(enum,tag) in enumerate([('ShortN','sn'),('ShortM','sm'),('Dense','dn')]):
        s+=f'    {"if" if i==0 else "else if"}(selection.strategy==Strategy::{enum}){{\n'+launch_family(tag,CONFIGS[tag][-1])+'    }\n'
    return s+'''#undef BMMS22_LAUNCH
    if(aclrtSynchronizeStream(stream)!=ACL_SUCCESS)std::abort();
    if(aclrtFree(ws)!=ACL_SUCCESS)std::abort();return true;
}
} // namespace bmms22
'''

def fragment(original):
    return '''// R22 shape-selected Native kernels. All policy decisions are HOST-only.
namespace bmms22 {
constexpr int32_t PACKET_TILES=4;
constexpr uint16_t READY=4,FREE=6;
__aicore__ inline int32_t MinI(int32_t a,int32_t b){return a<b?a:b;}
'''+(HERE/'host_plan.asc').read_text(encoding='utf-8')+'\n'+producer(original)+consumer(original)+kernels()+host_launch()

MARK='extern "C" void run_kernel(GM_ADDR a,const TensorGroupInfo& ia,'
OLD='    if(native){const auto p=bmms83::MakeNative(B,M,N,K,cores);uint8_t* ws=nullptr;'
NEW='''    if(native){
        if(bmms22::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;
        const auto p=bmms83::MakeNative(B,M,N,K,cores);uint8_t* ws=nullptr;'''

def verify():
    assert sha(BASE)==BASE_SHA and sha(OUT/'R14_CONTROL.asc')==BASE_SHA
    old=BASE.read_text(encoding='utf-8');frag=fragment(old);s=(OUT/(NAME+'.asc')).read_text(encoding='utf-8')
    assert frag==(HERE/'shape_fragment.asc').read_text(encoding='utf-8')
    restored=once(once(s,frag+'\n',''),NEW,OLD)
    assert restored.split('\n',1)[1]==old.split('\n',1)[1]
    entry=between(frag,'__aicore__ inline void Entry(','#endif\n} // namespace bmms22')
    assert 'Select(' not in entry and 'Strategy::' not in entry
    assert frag.count('BMMS22_KERNEL(bmms22_')==64
    return {'R14_preserved_outside_inserted_fragment_and_one_host_call':True,'all_strategy_selection_on_host':True,
        'three_fixed_device_geometries':True,'64_independent_kernel_bindings':True,'original_R14_fallback':True,
        'R20_R21_device_code_not_reused':True}

def main():
    assert sha(BASE)==BASE_SHA;OUT.mkdir(exist_ok=True);shutil.copyfile(BASE,OUT/'R14_CONTROL.asc')
    old=BASE.read_text(encoding='utf-8');frag=fragment(old);write(HERE/'shape_fragment.asc',frag)
    s=once(once(old,MARK,frag+'\n'+MARK),OLD,NEW)
    s=once(s,s.split('\n',1)[0],'// R22_SHAPE_SWITCH: host-selected ShortN/ShortM/Dense kernels, R14 fallback; pending CANN/NPU validation.')
    write(OUT/(NAME+'.asc'),s)
    write(HERE/(NAME+'.diff'),''.join(difflib.unified_diff(old.splitlines(True),s.splitlines(True),fromfile='R14',tofile=NAME)))
    report={'base':BASE.relative_to(ROOT).as_posix(),'base_sha256':BASE_SHA,'control':{'file':'R14_CONTROL.asc','sha256':BASE_SHA},
        'candidate':{'version':'R22','file':NAME+'.asc','sha256':sha(OUT/(NAME+'.asc')),'platform_result_received':False},
        'composition':verify(),'R20_status':'compile_failed_no_log_root_cause_unconfirmed','cann_compiled_locally':False,'npu_tested_locally':False}
    write(OUT/'MANIFEST.json',json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()

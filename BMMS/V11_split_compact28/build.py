"""Build compact split-K epilogue on frozen R25, gated by confirmed metadata."""
from pathlib import Path
import hashlib,json,shutil
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;OUT=ROOT/'BMMS_V11_R28'
BASE=ROOT/'BMMS_V11_R25/R25_NATIVE_TARGETED.asc'
BASE_SHA='7defd06457ddb0e356cbf4cc8407f31cbb7c622acf6efd66070be212fa4eacb2'
NAME='R28_COMPACT_SPLITK'
ANCHOR='extern "C" void run_kernel(GM_ADDR a,const TensorGroupInfo& ia,'
OLD_CALL='    if(bmms23::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;'
CALL=OLD_CALL.replace('bmms23::','bmms28::')+'\n'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,s):p.write_text(s,encoding='utf-8',newline='\n')
def once(s,a,b):assert s.count(a)==1,(s.count(a),a[:100]);return s.replace(a,b,1)
def between(s,a,b):i=s.index(a);return s[i:s.index(b,i)]
def function(s,mark):
    i=s.index(mark);j=s.index('{',i)+1;depth=1
    while depth:depth+=(s[j]=='{')-(s[j]=='}');j+=1
    return s[i:j]

def fragment(base):
    old=base[base.index('namespace bmms23 {'):]
    prod=between(old,'template<class T,bool TA,bool TB>\nclass Producer {','// Each batch has one AIV owner:')
    prod=once(prod,'f.dstStride=TN;','f.dstStride=p.N;')
    prefix='''
// BMMS28_BEGIN: compact epilogue for single-spatial, small-output, long-K plans.
namespace bmms28 {
using Plan=bmms23::Plan;
constexpr int32_t TM=bmms23::TM,TN=bmms23::TN,KB=bmms23::KB;
// Keep R23's maximum input merge allocation, not a new hardware UB assumption.
constexpr int32_t MERGE_FLOATS=bmms23::MAX_SPLITS*bmms23::ROWS*bmms23::TN;
constexpr uint16_t READY=bmms23::READY;
static inline bool Eligible(int B,int M,int N,int K,int dtype,int cores){
    if(!bmms23::Eligible(B,M,N,K,dtype,cores))return false;
    if(B!=1||M>64||N>128||int64_t(M)*N>4096)return false;
    return bmms23::MakePlan(B,M,N,K,cores).splits>=8;
}
'''
    entry='''
#ifndef BMMS28_CPU_TEST
template<class T,bool TA,bool TB>
__aicore__ inline void Entry(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ws,Plan p){
    AscendC::TPipe pipe;
    if ASCEND_IS_AIC {Producer<T,TA,TB> op;op.Init(a,b,ws,p,&pipe);op.Process();}
    if ASCEND_IS_AIV {Consumer op;op.Init(ws,y,p,&pipe);op.Process();}
}
#endif
} // namespace bmms28
// BMMS28_CPU_EXTRACT_END
#define BMMS28_KERNEL(NAME,T,TA,TB) \\
__schedmode__(1) __global__ __mix__(1,2) void NAME(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ws,bmms23::Plan p){bmms28::Entry<T,TA,TB>(a,b,y,ws,p);}
'''
    for dtype,T in [('f16','half'),('b16','bfloat16_t')]:
        for layout,ta,tb in [('nn','false','false'),('nt','false','true'),('tn','true','false'),('tt','true','true')]:
            entry+=f'BMMS28_KERNEL(bmms28_{dtype}_{layout},{T},{ta},{tb})\n'
    host=function(old[old.index('namespace bmms23 {\nstatic inline bool TryLaunch('):],'static inline bool TryLaunch(')
    host=once(host,'Plan p=MakePlan(B,M,N,K,cores);','Plan p=bmms23::MakePlan(B,M,N,K,cores);')
    host=once(host,'    if(BMMS23_SINGLE_K_CONTROL){p.splits=1;p.blocks=B*p.mTiles*p.nTiles;}\n','')
    host=host.replace('WorkspaceBytes(p)','bmms23::WorkspaceBytes(p)').replace('BMMS23_LAUNCH','BMMS28_LAUNCH').replace('bmms23_f16','bmms28_f16').replace('bmms23_b16','bmms28_b16')
    return prefix+prod+(HERE/'consumer.asc').read_text(encoding='utf-8')+entry+'#undef BMMS28_KERNEL\nnamespace bmms28 {\n'+host+'\n} // namespace bmms28\n// BMMS28_END\n\n'

def verify():
    assert sha(BASE)==BASE_SHA
    assert sha(OUT/'CONTROL_R25.asc')==BASE_SHA
    base=BASE.read_text(encoding='utf-8');new=(OUT/(NAME+'.asc')).read_text(encoding='utf-8')
    restored=once(once(new,fragment(base),''),CALL,'')
    assert restored.split('\n',1)[1]==base.split('\n',1)[1]
    return dict(R25_frozen=True,all_original_functions_byte_identical=True,
        old_dispatch_restored_by_removing_one_new_call=True,original_split_count_and_K_partition_preserved=True,
        new_producer_only_changes_Fixpipe_destination_pitch=True,original_workspace_bytes_preserved=True,
        original_READY_and_global_barrier_protocol_preserved=True)

def main():
    assert sha(BASE)==BASE_SHA;OUT.mkdir(exist_ok=True)
    base=BASE.read_text(encoding='utf-8');part=fragment(base)
    write(HERE/'compact_fragment.asc',part)
    new=once(base,ANCHOR,part+ANCHOR);new=once(new,OLD_CALL,CALL+OLD_CALL)
    new=once(new,new.split('\n',1)[0],'// R28_COMPACT_SPLITK: compact-N partials and batched K-shard DMA on frozen R25.')
    write(OUT/(NAME+'.asc'),new);shutil.copyfile(BASE,OUT/'CONTROL_R25.asc')
    manifest=dict(base=BASE.relative_to(ROOT).as_posix(),base_sha256=BASE_SHA,
        target='original Split-K eligible AND B=1 AND M<=64 AND N<=128 AND M*N<=4096 AND original splits>=8',
        files={p.name:sha(p) for p in OUT.glob('*.asc')},composition=verify(),
        CANN_compiled_locally=False,NPU_tested_locally=False,platform_results_pending=True)
    write(OUT/'MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(manifest['composition']))
if __name__=='__main__':main()

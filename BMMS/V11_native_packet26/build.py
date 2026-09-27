"""R26: packet-wide dense Native consumer on the exact R25 submission."""
from pathlib import Path
import hashlib,json,shutil
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;OUT=ROOT/'BMMS_V11_R26'
BASE=ROOT/'BMMS_V11_R25/R25_NATIVE_TARGETED.asc'
BASE_SHA='7defd06457ddb0e356cbf4cc8407f31cbb7c622acf6efd66070be212fa4eacb2'
NAME='R26_DENSE_PACKET';DENSE='p.K==128&&p.B==1&&p.M>32&&p.N>32&&p.blocks>1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,s):p.write_text(s,encoding='utf-8',newline='\n')
def once(s,a,b):assert s.count(a)==1,(s.count(a),a[:100]);return s.replace(a,b,1)
def between(s,a,b):i=s.index(a);return s[i:s.index(b,i)]
def function(s,mark):
    i=s.index(mark);j=s.index('{',i)+1;depth=1
    while depth:depth+=(s[j]=='{')-(s[j]=='}');j+=1
    return s[i:j]

def fragment(base):
    dense=between(base,'class DenseGatherConsumer {','template<class T,bool TA,bool TB,bool SMALL>\n__aicore__ inline void Entry(')
    dense=once(dense,'class DenseGatherConsumer {','class DensePacketConsumer {\n    static constexpr int HALF_TILE=(TM/2)*TN;')
    dense=once(dense,'    AscendC::TQue<AscendC::TPosition::VECIN,1> cq;\n','')
    dense=once(dense,'groupBuf,rowBuf,sumBuf;','groupBuf,rowBuf;')
    dense=once(dense,'mergedBuf,tmpBuf;','workBuf;')
    dense=once(dense,'public:\n',(HERE/'fetch_packet.asc').read_text(encoding='utf-8')+'public:\n')
    dense=once(dense,'pipe->InitBuffer(cq,1,(TM/2)*TN*4);pipe->InitBuffer(oq,1,32);','pipe->InitBuffer(oq,1,32);')
    dense=once(dense,'pipe->InitBuffer(runningBuf,AM*4);pipe->InitBuffer(mergedBuf,p.M*4);','pipe->InitBuffer(runningBuf,AM*4);')
    dense=once(dense,'pipe->InitBuffer(tmpBuf,mergeRows*p.pN*4);pipe->InitBuffer(sumBuf,p.M*4);',
        'const int mergeElements=2*p.M+mergeRows*p.pN;\n        const int workElements=mergeElements>PACKET_TILES*HALF_TILE?mergeElements:PACKET_TILES*HALF_TILE;\n        pipe->InitBuffer(workBuf,workElements*4);')
    dense=once(dense,'int seq=0;auto acc=', 'PacketCursor cursor;cursor.Init(p,group);\n        int seq=0;auto acc=')
    start=dense.index('                            if(tileSlot==0)AscendC::CrossCoreWaitFlag')
    end=dense.index('                            AscendC::Max(acc,acc,c,vr*TN);',start)
    dense=dense[:start]+'''                            if(tileSlot==0){
                                AscendC::CrossCoreWaitFlag<0x2>(READY+ringSlot);
                                FetchPacket(cursor,group,sub,ringSlot);
                            }
                            auto c=workBuf.Get<float>()[tileSlot*HALF_TILE];
'''+dense[end:]
    dense=once(dense,'cq.FreeTensor(c);++seq;','++seq;')
    dense=once(dense,'        // The final partial packet has no next tile to trigger the normal release.\n        if(seq%PACKET_TILES)AscendC::CrossCoreSetFlag<0x2,PIPE_MTE2>(FREE+((seq/PACKET_TILES)&1));\n','')
    dense=once(dense,'auto merged=mergedBuf.Get<float>(),values=tmpBuf.Get<float>();',
        '// Packet reads are complete. Reuse the same UB allocation for the merge.\n        bmms71::Fence<AscendC::HardEvent::V_MTE2>(*pipe_);\n        auto merged=workBuf.Get<float>(),values=merged[p.M];')
    dense=once(dense,'sumBuf.Get<float>()','merged[p.M+mergeRows*p.pN]')
    part='\n// BMMS26_BEGIN\nnamespace bmms26 {\nusing namespace bmms83;\n'+(HERE/'packet_helpers.asc').read_text(encoding='utf-8')+dense+'''
template<class T,bool TA,bool TB>
__aicore__ inline void Entry(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ring,GM_ADDR partial,NativePlan p){
    AscendC::TPipe pipe;
    if ASCEND_IS_AIC {bmms83::SmallKProducer<T,TA,TB,128> op;op.Init(a,b,ring,p,&pipe);op.Process();}
    if ASCEND_IS_AIV {DensePacketConsumer op;op.Init(ring,partial,y,p,&pipe);op.Process();}
}
} // namespace bmms26
// BMMS26_CPU_EXTRACT_END
#define BMMS26_KERNEL(NAME,T,TA,TB) \\
__schedmode__(1) __global__ __mix__(1,2) void NAME(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ring,GM_ADDR part,bmms83::NativePlan p){bmms26::Entry<T,TA,TB>(a,b,y,ring,part,p);}
'''
    for dtype,T in [('f16','half'),('b16','bfloat16_t')]:
        for layout,ta,tb in [('nn','false','false'),('nt','false','true'),('tn','true','false'),('tt','true','true')]:
            part+=f'BMMS26_KERNEL(bmms26_dense_{dtype}_{layout},{T},{ta},{tb})\n'
    hostbase=base[base.index('namespace bmms25 {\nstatic inline bool TryLaunch('):]
    host=function(hostbase,'static inline bool TryLaunch(')
    host=once(host,'const int strategy=Select(p);if(!strategy)return false;',f'if(!({DENSE}))return false;')
    lo=host.index('    if(strategy==1){');hi=host.index('\n    }else{\n',lo)+1
    host=host[:lo]+host[hi:].replace('    }else{\n','    {\n',1)
    host=host.replace('BMMS25_LAUNCH','BMMS26_LAUNCH').replace('bmms25_dense_','bmms26_dense_')
    return part+'#undef BMMS26_KERNEL\nnamespace bmms26 {\n'+host+'\n} // namespace bmms26\n// BMMS26_END\n\n'

ANCHOR='extern "C" void run_kernel(GM_ADDR a,const TensorGroupInfo& ia,GM_ADDR b,const TensorGroupInfo& ib,GM_ADDR y,const TensorGroupInfo& iy,'
HOOK='        if(bmms25::TryLaunch(a,b,y,p,x.dtype,ta,tb,stream))return;'
NEW_HOOK='        if(bmms26::TryLaunch(a,b,y,p,x.dtype,ta,tb,stream))return;\n'+HOOK
def verify():
    assert sha(BASE)==BASE_SHA
    base=BASE.read_text(encoding='utf-8');s=(OUT/(NAME+'.asc')).read_text(encoding='utf-8')
    restored=once(once(s,fragment(base),''),NEW_HOOK,HOOK)
    assert restored.split('\n',1)[1]==base.split('\n',1)[1]
    assert between(s,'// BMMS25_BEGIN','// BMMS25_END')==between(base,'// BMMS25_BEGIN','// BMMS25_END')
    assert sha(OUT/'CONTROL_R25.asc')==BASE_SHA
    return dict(R25_restorable_byte_identically_except_title=True,all_R25_kernels_unchanged=True,
        Case5_source_entry_plan_workspace_unchanged=True,original_Cube_producer_unchanged=True,
        Native_plan_and_workspace_unchanged=True,only_original_Native_B1_K128_MN_gt32_blocks_gt1_replaced=True)
def main():
    assert sha(BASE)==BASE_SHA;OUT.mkdir(exist_ok=True)
    base=BASE.read_text(encoding='utf-8');part=fragment(base);write(HERE/'packet_fragment.asc',part)
    code=once(once(base,HOOK,NEW_HOOK),ANCHOR,part+ANCHOR)
    code=once(code,code.split('\n',1)[0],'// R26_DENSE_PACKET: batch the Native B1 K128 consumer; preserve R25 small-batch kernels.')
    write(OUT/(NAME+'.asc'),code);shutil.copyfile(BASE,OUT/'CONTROL_R25.asc')
    manifest=dict(base=BASE.relative_to(ROOT).as_posix(),base_sha256=BASE_SHA,domain=DENSE,composition=verify(),
        files={p.name:sha(p) for p in OUT.glob('*.asc')},local_cann_compiled=False,local_npu_tested=False,platform_results_pending=True)
    write(OUT/'MANIFEST.json',json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest['composition']))
if __name__=='__main__':main()

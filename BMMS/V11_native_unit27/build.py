"""R27: isolated Native dense Mmad/Fixpipe UnitFlag candidate from frozen R25."""
from pathlib import Path
import hashlib,json,shutil
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;OUT=ROOT/'BMMS_V11_R27'
BASE=ROOT/'BMMS_V11_R25/R25_NATIVE_TARGETED.asc'
BASE_SHA='7defd06457ddb0e356cbf4cc8407f31cbb7c622acf6efd66070be212fa4eacb2'
NAME='R27_DENSE_UNITFLAG';DENSE='p.K==128&&p.B==1&&p.M>32&&p.N>32&&p.blocks>1'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,s):p.write_text(s,encoding='utf-8',newline='\n')
def once(s,a,b):assert s.count(a)==1,(s.count(a),a[:120]);return s.replace(a,b,1)
def between(s,a,b):i=s.index(a);return s[i:s.index(b,i)]
def function(s,mark):
    i=s.index(mark);j=s.index('{',i)+1;depth=1
    while depth:depth+=(s[j]=='{')-(s[j]=='}');j+=1
    return s[i:j]

def producer(base):
    original=between(base,'template<class T,bool TA,bool TB,int TK>\nclass SmallKProducer','class SmallKConsumer {')
    s=once(original,'class SmallKProducer {','class UnitProducer {')
    s=once(s,'abFree[2],cReady[2],cFree[2];','abFree[2],cFree[2];')
    s=once(s,'q.k=TK;q.cmatrixInitVal=true;','q.k=TK;q.cmatrixInitVal=true;q.unitFlag=3;')
    s=once(s,'        AscendC::Mmad(cc,aa,bb,q);',
        '        AscendC::Mmad(cc,aa,bb,q);\n        // Required dependency for small/tail MMADs after removing M_FIX.\n        if((mr/16)*(nr/16)<10)AscendC::PipeBarrier<PIPE_M>();')
    s=once(s,'        AscendC::SetFlag<AscendC::HardEvent::M_FIX>(cReady[slot]);\n        AscendC::WaitFlag<AscendC::HardEvent::M_FIX>(cReady[slot]);\n',
        '        // UnitFlag publishes each L0C unit to FIX; no whole-tile M_FIX wait.\n')
    s=once(s,'f.ndNum=1;f.quantPre=QuantMode_t::NoQuant;','f.ndNum=1;f.quantPre=QuantMode_t::NoQuant;f.unitFlag=3;')
    s=once(s,'            cReady[i]=pipe_->AllocEventID<AscendC::HardEvent::M_FIX>();\n','')
    s=once(s,'            pipe_->ReleaseEventID<AscendC::HardEvent::M_FIX>(cReady[i]);\n','')
    s=once(s,'        const int group=AscendC::GetBlockIdx();',
        '        // Match the existing NZ->ND Fixpipe traversal. Does not change K reduction.\n        AscendC::SetMMRowMajor();\n        const int group=AscendC::GetBlockIdx();')
    s=once(s,'            pipe_->ReleaseEventID<AscendC::HardEvent::FIX_M>(cFree[i]);\n        }\n',
        '            pipe_->ReleaseEventID<AscendC::HardEvent::FIX_M>(cFree[i]);\n        }\n        AscendC::SetMMColumnMajor(); // All MMAD/FIX work has drained.\n')
    assert 'M_FIX' not in s.replace('// Required dependency for small/tail MMADs after removing M_FIX.','').replace('// UnitFlag publishes each L0C unit to FIX; no whole-tile M_FIX wait.','')
    return s

def fragment(base):
    part='\n// BMMS27_BEGIN\nnamespace bmms27 {\nusing namespace bmms83;\n'+producer(base)+'''
template<class T,bool TA,bool TB>
__aicore__ inline void Entry(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ring,GM_ADDR partial,NativePlan p){
    AscendC::TPipe pipe;
    if ASCEND_IS_AIC {UnitProducer<T,TA,TB,128> op;op.Init(a,b,ring,p,&pipe);op.Process();}
    if ASCEND_IS_AIV {bmms25::DenseGatherConsumer op;op.Init(ring,partial,y,p,&pipe);op.Process();}
}
} // namespace bmms27
// BMMS27_CPU_EXTRACT_END
#define BMMS27_KERNEL(NAME,T,TA,TB) \\
__schedmode__(1) __global__ __mix__(1,2) void NAME(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ring,GM_ADDR part,bmms83::NativePlan p){bmms27::Entry<T,TA,TB>(a,b,y,ring,part,p);}
'''
    for dtype,T in [('f16','half'),('b16','bfloat16_t')]:
        for layout,ta,tb in [('nn','false','false'),('nt','false','true'),('tn','true','false'),('tt','true','true')]:
            part+=f'BMMS27_KERNEL(bmms27_dense_{dtype}_{layout},{T},{ta},{tb})\n'
    hostbase=base[base.index('namespace bmms25 {\nstatic inline bool TryLaunch('):]
    host=function(hostbase,'static inline bool TryLaunch(')
    host=once(host,'const int strategy=Select(p);if(!strategy)return false;',f'if(!({DENSE}))return false;')
    lo=host.index('    if(strategy==1){');hi=host.index('\n    }else{\n',lo)+1
    host=host[:lo]+host[hi:].replace('    }else{\n','    {\n',1)
    host=host.replace('BMMS25_LAUNCH','BMMS27_LAUNCH').replace('bmms25_dense_','bmms27_dense_')
    return part+'#undef BMMS27_KERNEL\nnamespace bmms27 {\n'+host+'\n} // namespace bmms27\n// BMMS27_END\n\n'

ANCHOR='extern "C" void run_kernel(GM_ADDR a,const TensorGroupInfo& ia,GM_ADDR b,const TensorGroupInfo& ib,GM_ADDR y,const TensorGroupInfo& iy,'
HOOK='        if(bmms25::TryLaunch(a,b,y,p,x.dtype,ta,tb,stream))return;'
NEW_HOOK='        if(bmms27::TryLaunch(a,b,y,p,x.dtype,ta,tb,stream))return;\n'+HOOK

def verify():
    assert sha(BASE)==BASE_SHA
    base=BASE.read_bytes().decode('utf-8');s=(OUT/(NAME+'.asc')).read_bytes().decode('utf-8')
    restored=once(once(s,fragment(base),''),NEW_HOOK,HOOK)
    assert restored.split('\n',1)[1].encode()==BASE.read_bytes().split(b'\n',1)[1]
    assert between(s,'// BMMS25_BEGIN','// BMMS25_END')==between(base,'// BMMS25_BEGIN','// BMMS25_END')
    assert sha(OUT/'CONTROL_R25.asc')==BASE_SHA
    assert 'bmms26' not in s
    return dict(R25_restorable_byte_identically_except_title=True,all_R25_kernels_unchanged=True,
        Case5_source_entry_plan_workspace_unchanged=True,R25_dense_consumer_unchanged=True,
        Native_plan_workspace_and_shapes_unchanged=True,packet_READY_FREE_and_FIX_M_reuse_unchanged=True,
        only_original_Native_B1_K128_MN_gt32_blocks_gt1_replaced=True,R26_consumer_not_carried=True)

def main():
    assert sha(BASE)==BASE_SHA;OUT.mkdir(exist_ok=True)
    base=BASE.read_text(encoding='utf-8');part=fragment(base);write(HERE/'unit_fragment.asc',part)
    code=once(once(base,HOOK,NEW_HOOK),ANCHOR,part+ANCHOR)
    code=once(code,code.split('\n',1)[0],'// R27_DENSE_UNITFLAG: Native B1 K128 Cube handoff; preserve every R25 consumer and small-batch kernel.')
    write(OUT/(NAME+'.asc'),code);shutil.copyfile(BASE,OUT/'CONTROL_R25.asc')
    manifest=dict(base=BASE.relative_to(ROOT).as_posix(),base_sha256=BASE_SHA,domain=DENSE,composition=verify(),
        files={p.name:sha(p) for p in OUT.glob('*.asc')},local_cann_compiled=False,local_npu_tested=False,platform_results_pending=True)
    write(OUT/'MANIFEST.json',json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest['composition']))
if __name__=='__main__':main()

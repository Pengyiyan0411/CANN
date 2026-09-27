"""Two disjoint Native K128 specializations on frozen R23; no planner changes."""
from pathlib import Path
import hashlib,json,shutil
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;OUT=ROOT/'BMMS_V11_R25'
BASE=ROOT/'BMMS_V11_R23/R23_SPLIT_K.asc'
BASE_SHA='d097fdc60ffc8be7ddf40ef93a3afa04c04d904fec4ae8b42dc7085238353733'
VARIANTS={'R25_NATIVE_TARGETED':(1,1),'R25_SMALL_ONLY':(1,0),'R25_DENSE_ONLY':(0,1)}
SMALL='p.K==128&&p.B>1&&p.M<=32&&p.N<=32&&p.blocks>1'
DENSE='p.K==128&&p.B==1&&p.M>32&&p.N>32&&p.blocks>1'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,s):p.write_text(s,encoding='utf-8',newline='\n')
def once(s,a,b):assert s.count(a)==1,(s.count(a),a[:120]);return s.replace(a,b,1)
def between(s,a,b):i=s.index(a);return s[i:s.index(b,i)]
def function(s,mark):
    i=s.index(mark);j=s.index('{',i)+1;depth=1
    while depth:depth+=(s[j]=='{')-(s[j]=='}');j+=1
    return s[i:j]

def fragment(base):
    small=(HERE/'small_consumer.asc').read_text(encoding='utf-8')
    dense=between(base,'class SmallKPacketConsumer {','template<class T,bool TA,bool TB,int TK>\n__aicore__ inline void NativeEntry(')
    dense=once(dense,'class SmallKPacketConsumer {','class DenseGatherConsumer {')
    dense=once(dense,'NativePlan p;AscendC::TPipe* pipe_;','NativePlan p;AscendC::TPipe* pipe_;int mergeRows;')
    dense=once(dense,'pipe->InitBuffer(tmpBuf,p.M*4);','mergeRows=MinI(p.M,(16384/p.pN/16)*16);\n        pipe->InitBuffer(tmpBuf,mergeRows*p.pN*4);')
    start=dense.index('        auto merged=mergedBuf.Get<float>(),tmp=tmpBuf.Get<float>();')
    assert dense[start:].endswith('    }\n};\n\n')
    dense=dense[:start]+(HERE/'dense_merge.asc').read_text(encoding='utf-8')+'    }\n};\n\n'
    host=f'''static inline int Select(const NativePlan& p){{
    if(BMMS25_SMALL&&{SMALL})return 1;
    if(BMMS25_DENSE&&{DENSE})return 2;
    return 0;
}}
'''
    part='\n// BMMS25_BEGIN\nnamespace bmms25 {\nusing namespace bmms83;\n'+host+small+'\n'+dense+'''
template<class T,bool TA,bool TB,bool SMALL>
__aicore__ inline void Entry(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ring,GM_ADDR partial,NativePlan p){
    AscendC::TPipe pipe;
    if ASCEND_IS_AIC {bmms83::SmallKProducer<T,TA,TB,128> op;op.Init(a,b,ring,p,&pipe);op.Process();}
    if ASCEND_IS_AIV {
        if constexpr(SMALL){SmallBatchConsumer op;op.Init(ring,partial,y,p,&pipe);op.Process();}
        else{DenseGatherConsumer op;op.Init(ring,partial,y,p,&pipe);op.Process();}
    }
}
} // namespace bmms25
// BMMS25_CPU_EXTRACT_END
#define BMMS25_KERNEL(NAME,T,TA,TB,SMALL) \\
__schedmode__(1) __global__ __mix__(1,2) void NAME(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ring,GM_ADDR part,bmms83::NativePlan p){bmms25::Entry<T,TA,TB,SMALL>(a,b,y,ring,part,p);}
'''
    for mode,flag in [('small','true'),('dense','false')]:
        for dtype,T in [('f16','half'),('b16','bfloat16_t')]:
            for layout,ta,tb in [('nn','false','false'),('nt','false','true'),('tn','true','false'),('tt','true','true')]:
                part+=f'BMMS25_KERNEL(bmms25_{mode}_{dtype}_{layout},{T},{ta},{tb},{flag})\n'
    part+='''#undef BMMS25_KERNEL
namespace bmms25 {
static inline bool TryLaunch(GM_ADDR a,GM_ADDR b,GM_ADDR y,const NativePlan& p,int dtype,bool ta,bool tb,aclrtStream stream){
    const int strategy=Select(p);if(!strategy)return false;
    uint8_t* ws=nullptr;const uint64_t rb=NativeRingBytes(p),pb=NativePartialBytes(p);
    if(aclrtMalloc(reinterpret_cast<void**>(&ws),rb+pb,ACL_MEM_MALLOC_HUGE_FIRST)!=ACL_SUCCESS)std::abort();
    uint8_t* partial=ws+rb;
#define BMMS25_LAUNCH(NAME) NAME<<<p.blocks,nullptr,stream>>>(a,b,y,ws,partial,p)
'''
    for index,mode in enumerate(['small','dense']):
        part+=('    if(strategy==1){\n' if index==0 else '    }else{\n')
        for j,dtype in enumerate(['f16','b16']):
            part+=('        if(dtype==1){\n' if j==0 else '        }else{\n')
            part+=f'            if(!ta&&!tb){{BMMS25_LAUNCH(bmms25_{mode}_{dtype}_nn);}}else if(!ta&&tb){{BMMS25_LAUNCH(bmms25_{mode}_{dtype}_nt);}}\n'
            part+=f'            else if(ta&&!tb){{BMMS25_LAUNCH(bmms25_{mode}_{dtype}_tn);}}else{{BMMS25_LAUNCH(bmms25_{mode}_{dtype}_tt);}}\n'
        part+='        }\n'
    part+='''    }
#undef BMMS25_LAUNCH
    if(aclrtSynchronizeStream(stream)!=ACL_SUCCESS)std::abort();
    if(aclrtFree(ws)!=ACL_SUCCESS)std::abort();return true;
}
} // namespace bmms25
// BMMS25_END

'''
    return part

HOOK='if(native){const auto p=bmms83::MakeNative(B,M,N,K,cores);uint8_t* ws=nullptr;'
NEW_HOOK='if(native){const auto p=bmms83::MakeNative(B,M,N,K,cores);\n        if(bmms25::TryLaunch(a,b,y,p,x.dtype,ta,tb,stream))return;\n        uint8_t* ws=nullptr;'
ANCHOR='extern "C" void run_kernel(GM_ADDR a,const TensorGroupInfo& ia,GM_ADDR b,const TensorGroupInfo& ib,GM_ADDR y,const TensorGroupInfo& iy,'

def verify():
    assert sha(BASE)==BASE_SHA
    base=BASE.read_text(encoding='utf-8');part=fragment(base)
    for name,(small,dense) in VARIANTS.items():
        s=(OUT/(name+'.asc')).read_text(encoding='utf-8')
        defs=f'#define BMMS25_SMALL {small}\n#define BMMS25_DENSE {dense}\n'
        restored=once(once(once(s,defs,''),part,''),NEW_HOOK,HOOK)
        assert restored.split('\n',1)[1]==base.split('\n',1)[1],name
    return {'frozen_R23':True,'all_original_functions_byte_identical':True,'Native_plan_unchanged':True,
            'Cube_and_packet_producer_unchanged':True,'earlier_routes_and_fallback_unchanged':True,
            'only_selects_inside_actual_Native_branch':True,'small_and_dense_domains_disjoint':True}

def main():
    assert sha(BASE)==BASE_SHA;OUT.mkdir(exist_ok=True)
    base=BASE.read_text(encoding='utf-8');part=fragment(base);write(HERE/'targeted_fragment.asc',part)
    shutil.copyfile(BASE,OUT/'CONTROL_R23.asc')
    for name,(small,dense) in VARIANTS.items():
        code=once(base,HOOK,NEW_HOOK);code=once(code,ANCHOR,part+ANCHOR)
        code=once(code,code.split('\n',1)[0],f'// {name}: metadata-gated Native K128 consumers on frozen R23.\n#define BMMS25_SMALL {small}\n#define BMMS25_DENSE {dense}')
        write(OUT/(name+'.asc'),code)
    manifest={'base':BASE.relative_to(ROOT).as_posix(),'base_sha256':BASE_SHA,'domains':{'small':SMALL,'dense':DENSE},
        'variants':VARIANTS,'composition':verify(),'files':{p.name:sha(p) for p in OUT.glob('*.asc')},
        'local_cann_compiled':False,'local_npu_tested':False,'platform_results_pending':True}
    write(OUT/'MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');print(json.dumps(manifest['composition']))
if __name__=='__main__':main()

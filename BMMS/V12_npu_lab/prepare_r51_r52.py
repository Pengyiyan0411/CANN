"""K1-only experiments, each independently based on the frozen r41 source."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
V = ROOT / 'BMMS_V12'
LAB = ROOT / 'V12_npu_lab/case12_k1_20261001'
LAB.mkdir(exist_ok=True)
base = (V / 'v12_baseline_r41.asc').read_bytes().decode()
assert hashlib.sha256(base.encode()).hexdigest() == '1caf7870ac4154c0f555621ba9c41f4601c6ecee96cb2e8d0bf23acc4fc4f373'
a = base.index('template<class T,bool TA,bool TB>\nclass MacroMmadProducer', base.index('namespace bmms1230 {'))
b = base.index('class RowMaxConsumer {', a)
producer = base[a:b]
scope = '''static inline bool Eligible(int B,int M,int N,int K,int cores){
    if(cores<2 || !bmms1230::Eligible(B,M,N,K,cores) ||
       !(M>=1280 && M<1536 && N>=4096 && N<6144 && K==1536) ||
       bmms1241::Eligible(B,M,N,K,cores))return false;
    const auto p=MakePlan(B,M,N,K,cores);
    return p.pN==2 && p.pM>=8 && p.pM==p.mTiles && p.tasks==cores && p.blocks==cores;
}
'''
for version,k1 in [(51,320),(52,192)]:
    ns=f'bmms12{version}'
    mod=f'''// BMMS12{version}_BEGIN
// Independent r41 experiment: K1={k1}; K0 order, grid and row-max consumer unchanged.
namespace {ns} {{
using Plan=bmms1230::Plan;using bmms1230::MakePlan;using bmms1230::AlignedPitch;using bmms83::MinI;
constexpr int TM=64,TN=128,AM=128,BN=256,K1={k1},K0=64,MACRO_ELEMS=AM*BN;
constexpr uint16_t READY=4,FREE=6;
static_assert(2*(AM+BN)*K1*2<=512*1024,"L1 buffers exceed 512 KiB");
'''+scope+producer+'''
template<class T,bool TA,bool TB>
__aicore__ inline void Entry(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ring,GM_ADDR part,Plan p){
    AscendC::TPipe pipe;
    if ASCEND_IS_AIC {MacroMmadProducer<T,TA,TB> op;op.Init(a,b,ring,p,&pipe);op.Process();}
    if ASCEND_IS_AIV {bmms1230::RowMaxConsumer op;op.Init(ring,part,y,p,&pipe);op.Process();}
}
}
'''
    macro=f'BMMS12{version}_KERNEL'
    mod+=f'#define {macro}(NAME,T,TA) \\\n__schedmode__(1) __global__ __mix__(1,2) void NAME(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ring,GM_ADDR part,{ns}::Plan p){{{ns}::Entry<T,TA,false>(a,b,y,ring,part,p);}}\n'
    # TB=true is explicitly excluded before dispatch. Only four entries are needed.
    for dt,T in [('f16','half'),('b16','bfloat16_t')]:
        for ta in [False,True]:mod+=f'{macro}({ns}_{dt}_{"tn" if ta else "nn"},{T},{str(ta).lower()})\n'
    mod+=f'''#undef {macro}
namespace {ns} {{
static inline bool TryLaunch(GM_ADDR a,GM_ADDR b,GM_ADDR y,int32_t B,int32_t M,int32_t N,int32_t K,
    int32_t dtype,bool ta,bool tb,int32_t cores,aclrtStream stream){{
    if(tb || (dtype!=1&&dtype!=2) || !Eligible(B,M,N,K,cores) || !AlignedPitch(M,N,K,ta,tb))return false;
    const auto family=bmms8::Classify(B,M,N,K,ta,tb);
    if(family==bmms8::Family::Resident||family==bmms8::Family::Tiny)return false;
    const auto p=MakePlan(B,M,N,K,cores);uint8_t* ws=nullptr;
    if(aclrtMalloc(reinterpret_cast<void**>(&ws),bmms11r2::WorkspaceBytes(p),ACL_MEM_MALLOC_HUGE_FIRST)!=ACL_SUCCESS)std::abort();
    uint8_t* partial=ws+bmms11r2::RingBytes(p);
#define BMMS12{version}_LAUNCH(NAME) NAME<<<p.blocks,nullptr,stream>>>(a,b,y,ws,partial,p)
    if(dtype==1){{
        if(ta){{BMMS12{version}_LAUNCH({ns}_f16_tn);}}else{{BMMS12{version}_LAUNCH({ns}_f16_nn);}}
    }}else{{
        if(ta){{BMMS12{version}_LAUNCH({ns}_b16_tn);}}else{{BMMS12{version}_LAUNCH({ns}_b16_nn);}}
    }}
#undef BMMS12{version}_LAUNCH
    if(aclrtSynchronizeStream(stream)!=ACL_SUCCESS)std::abort();if(aclrtFree(ws)!=ACL_SUCCESS)std::abort();return true;
}}
}}
// BMMS12{version}_END

'''
    hook=f'    if({ns}::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
    i=base.index('extern "C" void run_kernel(')
    src=base[:i]+mod+base[i:]
    i=src.index('    if(bmms1241::TryLaunch')
    src=src[:i]+hook+src[i:]
    assert src.replace(mod,'',1).replace(hook,'',1)==base
    name=f'v12_r{version}_case12_kstage{k1}.asc'
    (V/name).write_bytes(src.encode());(LAB/f'r{version}.asc').write_bytes(src.encode())
    meta=dict(version=f'v12_r{version}',parent='v12_baseline_r41.asc',sha256=hashlib.sha256(src.encode()).hexdigest(),K1=k1,
              scope='B=1,1280<=M<1536,4096<=N<6144,K=1536,TB=false,pN=2,pM=mTiles>=8,tasks=blocks=cores,r41 gate false,pitch aligned',
              changes='K1 only; producer implementation byte-identical to r30; original consumer reused',
              status='experimental pending NPU validation',parent_byte_recovery=True,new_device_entries=4)
    (V/f'v12_r{version}_manifest.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(meta))
(LAB/'r41.asc').write_bytes(base.encode())
main=(ROOT/'V12_npu_lab/narrow_dense/main.asc').read_text()
old='target=B==1&&M>=1024&&N>=1024&&K>=1024&&K<1536&&p.nTiles/p.pN>=2;'
new='target=B==1&&M>=1280&&M<1536&&N>=4096&&N<6144&&K==1536&&!tb&&bmms1230::AlignedPitch(M,N,K,ta,tb)&&!bmms1241::Eligible(B,M,N,K,cores)&&p.pN==2&&p.pM>=8&&p.pM==p.mTiles&&p.tasks==cores&&p.blocks==cores;'
assert old in main
main=main.replace(old,new).replace('r06_guard','case12_k1_guard')
(LAB/'main.asc').write_bytes(main.encode())
screen=(ROOT/'V12_npu_lab/narrow_dense/run_screen.py').read_text().replace('timeout=150','timeout=300')
(LAB/'run_screen.py').write_bytes(screen.encode())
(LAB/'CMakeLists.txt').write_text('''cmake_minimum_required(VERSION 3.16)
find_package(ASC REQUIRED)
project(bmms_case12_k1 LANGUAGES ASC CXX)
set(CMAKE_CXX_STANDARD 14)
foreach(v r41 r51 r52)
 add_executable(bench_${v} main.asc)
 target_compile_definitions(bench_${v} PRIVATE BMMS_KERNEL_HEADER="${v}.asc" BMMS_VARIANT="${v}")
 target_link_libraries(bench_${v} PRIVATE tiling_api register platform unified_dlog dl m graph_base)
 target_include_directories(bench_${v} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
 target_compile_options(bench_${v} PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=dav-2201>)
endforeach()
''',encoding='utf-8')

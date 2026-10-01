from pathlib import Path
import hashlib,json,tarfile
root=Path(__file__).resolve().parents[1]
lab=root/'V12_npu_lab/rethink_20261001';lab.mkdir(exist_ok=True)
out=root/'V12_npu_lab/results/rethink_20261001';out.mkdir(exist_ok=True)
base=(root/'BMMS_V12/v12_baseline_r41.asc').read_bytes().decode('utf-8')
assert hashlib.sha256(base.encode()).hexdigest()=='1caf7870ac4154c0f555621ba9c41f4601c6ecee96cb2e8d0bf23acc4fc4f373'
(lab/'r41.asc').write_bytes(base.encode())
(lab/'main.asc').write_bytes((root/'V12_npu_lab/case12_k1_20261001/main.asc').read_bytes())
(lab/'run_screen.py').write_bytes((root/'V12_npu_lab/case12_k1_20261001/run_screen.py').read_bytes())
# An extraction with the SAME per-core plan/K order, replacing ring stores by full C stores.
a=base.index('template<class T,bool TA,bool TB>\nclass MacroMmadProducer',base.index('// BMMS1230_BEGIN'))
b=base.index('class RowMaxConsumer',a)
producer=base[a:b]
producer=producer.replace('if(seq>=2)AscendC::CrossCoreWaitFlag<0x2>(FREE+macroSlot);','')
producer=producer.replace('f.dstStride=BN;','f.dstStride=p.N;')
producer=producer.replace('ring[(int64_t(group)*2+macroSlot)*MACRO_ELEMS]','ring[(int64_t(batch)*p.M+m0)*p.N+n0]')
producer=producer.replace('AscendC::CrossCoreSetFlag<0x2,PIPE_FIX>(READY+macroSlot);++seq;','++seq;')
producer=producer.replace('int64_t(p.blocks)*2*MACRO_ELEMS','int64_t(p.B)*p.M*p.N')
producer=producer.replace('for(int s=0;s<MinI(2,seq);++s)AscendC::CrossCoreWaitFlag<0x2>(FREE+s);','')
assert 'CrossCore' not in producer
prefix='#define run_kernel run_kernel_frozen\n#include "r41.asc"\n#undef run_kernel\nnamespace audit_gemm {\nusing namespace bmms1230;\n'
suffix='''
template<class T,bool TA> __global__ __aicore__ void bmms_audit_native(GM_ADDR a,GM_ADDR b,GM_ADDR c,Plan p){
 KERNEL_TASK_TYPE_DEFAULT(KERNEL_TYPE_AIC_ONLY);
 AscendC::TPipe pipe;MacroMmadProducer<T,TA,false> op;op.Init(a,b,c,p,&pipe);op.Process();
}
static inline void launch(GM_ADDR a,GM_ADDR b,GM_ADDR c,int M,int N,int K,int dt,bool ta,int cores,aclrtStream stream){
 auto p=bmms1230::MakePlan(1,M,N,K,cores);
 if(dt==1){if(ta)bmms_audit_native<half,true><<<p.blocks,nullptr,stream>>>(a,b,c,p);else bmms_audit_native<half,false><<<p.blocks,nullptr,stream>>>(a,b,c,p);}
 else{if(ta)bmms_audit_native<bfloat16_t,true><<<p.blocks,nullptr,stream>>>(a,b,c,p);else bmms_audit_native<bfloat16_t,false><<<p.blocks,nullptr,stream>>>(a,b,c,p);}
}
}
'''
(lab/'native_gemm.asc').write_text(prefix+producer+suffix,encoding='utf-8',newline='\n')
catlass=root/'V9_design/references/catlass'
with tarfile.open(lab/'catlass_headers.tar.gz','w:gz') as tar:
 for name in ['include','LICENSE']:
  tar.add(catlass/name,arcname='catlass/'+name)
cm='''cmake_minimum_required(VERSION 3.16)
find_package(ASC REQUIRED)
project(bmms_rethink LANGUAGES ASC CXX)
set(CMAKE_CXX_STANDARD 17)
foreach(v native cat0 cat1)
 add_executable(gemm_${v} gemm_main.asc)
 target_compile_definitions(gemm_${v} PRIVATE AUDIT_VARIANT="${v}")
 target_link_libraries(gemm_${v} PRIVATE tiling_api register platform unified_dlog dl m graph_base)
 target_include_directories(gemm_${v} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR} ${CMAKE_CURRENT_SOURCE_DIR}/catlass/include)
 target_compile_options(gemm_${v} PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=dav-2201>)
endforeach()
target_compile_definitions(gemm_native PRIVATE AUDIT_NATIVE=1)
target_compile_definitions(gemm_cat0 PRIVATE AUDIT_UNIT=0)
target_compile_definitions(gemm_cat1 PRIVATE AUDIT_UNIT=1)
foreach(v r41)
 add_executable(bench_${v} main.asc)
 target_compile_definitions(bench_${v} PRIVATE BMMS_KERNEL_HEADER="${v}.asc" BMMS_VARIANT="${v}")
 target_link_libraries(bench_${v} PRIVATE tiling_api register platform unified_dlog dl m graph_base)
 target_compile_options(bench_${v} PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=dav-2201>)
endforeach()
'''
(lab/'CMakeLists.txt').write_text(cm,encoding='utf-8',newline='\n')
print(lab)

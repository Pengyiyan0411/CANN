from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1];out=root/'BMMS_V12';lab=root/'V12_npu_lab/narrow_dense'
base=(out/'v12_r37_dense_singlewave_plan.asc').read_bytes();raw=base.decode()
pos=raw.index('namespace bmms1230 {')
a=raw.index('class RowMaxConsumer {',pos);b=raw.index('} // namespace bmms1230',a)
consumer=raw[a:b]
consumer=consumer.replace('mergedBuf,tmpBuf;', 'mergedBuf;')
consumer=consumer.replace('pipe->InitBuffer(mergedBuf,p.M*4);pipe->InitBuffer(tmpBuf,p.M*4);pipe->InitBuffer(sumBuf,p.M*4);',
 'pipe->InitBuffer(mergedBuf,p.pN*p.M*4);pipe->InitBuffer(sumBuf,p.M*4);')
consumer=consumer.replace('auto merged=mergedBuf.Get<float>(),tmp=tmpBuf.Get<float>();','auto merged=mergedBuf.Get<float>();')
consumer=consumer.replace('AscendC::DataCopy(merged,part[start],p.M);','AscendC::DataCopy(merged,part[start],p.pN*p.M);')
old='AscendC::DataCopy(tmp,part[start+int64_t(ns)*p.M],p.M);bmms71::Fence<AscendC::HardEvent::MTE2_V>(*pipe_);'
assert old in consumer
consumer=consumer.replace(old,'auto tmp=merged[ns*p.M];')
consumer=consumer.replace('bmms71::Fence<AscendC::HardEvent::V_MTE2>(*pipe_);\n            }','AscendC::PipeBarrier<PIPE_V>();\n            }')
assert 'tmpBuf' not in consumer
mod='''// BMMS1238_BEGIN
namespace bmms1238 {
using Plan=bmms1230::Plan;using bmms1230::MakePlan;
using bmms83::MinI;
constexpr int AM=bmms1230::AM,BN=bmms1230::BN;
constexpr int MACRO_ELEMS=bmms1230::MACRO_ELEMS;
constexpr int READY=bmms1230::READY,FREE=bmms1230::FREE;
static inline bool UsePacked(const Plan& p){
    const uint64_t ub=uint64_t(AM/2)*BN*4+32+2*(AM/2)*4+uint64_t(p.pN+1)*p.M*4;
    return bmms1237::InDomain(p.B,p.M,p.N,p.K)&&p.pN>=4&&ub<=192*1024;
}
'''+consumer+'''
template<class T,bool TA,bool TB>
__aicore__ inline void Entry(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ring,GM_ADDR part,Plan p){
    AscendC::TPipe pipe;
    if ASCEND_IS_AIC {bmms1230::MacroMmadProducer<T,TA,TB> op;op.Init(a,b,ring,p,&pipe);op.Process();}
    if ASCEND_IS_AIV {RowMaxConsumer op;op.Init(ring,part,y,p,&pipe);op.Process();}
}
}
'''
start=raw.index('#define BMMS1230_KERNEL');end=raw.index('// BMMS1230_END',start)
launch=raw[start:end].replace('1230','1238')
launch=launch.replace('!Eligible(B,M,N,K,cores)||!AlignedPitch(M,N,K,ta,tb)', '!bmms1230::Eligible(B,M,N,K,cores)||!bmms1230::AlignedPitch(M,N,K,ta,tb)')
launch=launch.replace('const auto p=MakePlan(B,M,N,K,cores);uint8_t* ws=nullptr;', 'const auto p=MakePlan(B,M,N,K,cores);if(!UsePacked(p))return false;uint8_t* ws=nullptr;')
mod+=launch+'// BMMS1238_END\n'
idx=raw.index('extern "C" void run_kernel');data=raw[:idx]+mod+'\n'+raw[idx:]
hook='    if(bmms1238::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
idx=data.index('    if(bmms1230::TryLaunch');data=data[:idx]+hook+data[idx:]
assert data.replace(mod+'\n','',1).replace(hook,'',1).encode()==base
name='v12_r38_dense_packed_merge.asc';(out/name).write_bytes(data.encode());(lab/'r38.asc').write_bytes(data.encode())
event=(lab/'event_plans.asc').read_text()
event=event.replace('auto p=candidate?bmms1237::MakePlan(plan.B,plan.M,plan.N,plan.K,20):plan;', 'auto p=plan;')
event=event.replace('DISPATCH(bmms1230);','if(candidate&&bmms1238::UsePacked(p)){DISPATCH(bmms1238);}else{DISPATCH(bmms1230);}')
event=event.replace('const auto p=bmms11r2::MakePlan','const auto p=bmms1237::MakePlan')
event=event.replace('candidate?"r37":"r33"','candidate?"r38":"r37"')
(lab/'event_merge.asc').write_text(event)
cm=(lab/'CMakeLists.txt').read_text()
cm+='''
add_executable(event_merge event_merge.asc)
add_executable(bench_r38 main.asc)
foreach(t event_merge bench_r38)
 target_compile_definitions(${t} PRIVATE BMMS_KERNEL_HEADER="r38.asc" BMMS_VARIANT="r38")
 target_link_libraries(${t} PRIVATE tiling_api register platform unified_dlog dl m graph_base)
 target_include_directories(${t} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
 target_compile_options(${t} PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=dav-2201>)
endforeach()
'''
(lab/'CMakeLists.txt').write_text(cm)
manifest=dict(version='v12_r38',parent='v12_r37_dense_singlewave_plan.asc',accepted_baseline='v12_baseline_r33.asc',sha256=hashlib.sha256(data.encode()).hexdigest(),status='experimental, pending tests',new_device_entries=8,source_byte_recovery=True)
(out/'v12_r38_manifest.json').write_text(json.dumps(manifest,indent=2));print(manifest)

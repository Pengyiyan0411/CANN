from pathlib import Path
root=Path(__file__).resolve().parents[1];lab=root/'V13_npu_lab/c12_merge_20261001'
base=(root/'BMMS_V12/v12_baseline_r41.asc').read_text();mod=(lab/'c12_module.asc').read_text()
def extract(start,end):return base[base.index(start):base.index(end,base.index(start))]
plan=extract('struct NativePlan {','static inline bool NativeEligible')
eligible=extract('static inline bool Eligible(int32_t B,int32_t M,int32_t N,int32_t K,int32_t cores){','// Closed-form peak work')
fence=extract('template<AscendC::HardEvent E>\n__aicore__ inline void Fence(AscendC::TPipe& pipe){','// Small resident GEMM')
prefix='''#include <cstdint>
#include <cstdlib>
#include "acl/acl.h"
#include "kernel_operator.h"
using namespace AscendC;
namespace bmms83 {
__aicore__ inline int32_t MinI(int32_t a,int32_t b){return a<b?a:b;}
static inline int32_t UpH(int32_t a,int32_t b){return (a+b-1)/b;}
static inline int32_t MinH(int32_t a,int32_t b){return a<b?a:b;}
static inline int32_t MaxH(int32_t a,int32_t b){return a>b?a:b;}
'''+plan+'''}
namespace bmms11r2 {
using Plan=bmms83::NativePlan;
constexpr int AM=128,BN=256,K1=256,MACRO_ELEMS=32768;
'''+eligible+'''
static inline uint64_t RingBytes(const Plan& p){return uint64_t(p.blocks)*2*MACRO_ELEMS*4ULL;}
static inline uint64_t PartialBytes(const Plan& p){return uint64_t(p.B)*p.pN*p.M*4ULL;}
static inline uint64_t WorkspaceBytes(const Plan& p){return RingBytes(p)+PartialBytes(p);}
}
namespace bmms71 {
'''+fence+'''}
namespace bmmmaxsum_v43 {constexpr float NEG_INF=-__builtin_inff();}
// Host-only classification stub: the focused harness admits only the C12 domain.
namespace bmms8 {enum class Family{Resident,Tiny,Dense_LargeK}; static inline Family Classify(int,int,int,int,bool,bool){return Family::Dense_LargeK;} }
namespace bmms52 {static inline bool Eligible(int,int,int,int){return false;} }
'''
suffix='''
extern "C" void run_kernel(GM_ADDR a,const TensorGroupInfo& ia,GM_ADDR b,const TensorGroupInfo& ib,GM_ADDR y,const TensorGroupInfo& iy,int64_t availableCoreNum,aclrtStream stream,bool ta,bool tb){
 const auto& x=ia.tensors[0];const auto& z=ib.tensors[0];
 const int B=x.shape[0],M=x.shape[ta?2:1],K=x.shape[ta?1:2],N=z.shape[tb?1:2];
 if(!bmms12opt::TryLaunch(a,b,y,B,M,N,K,x.dtype,ta,tb,int(availableCoreNum),stream))std::abort();
}
'''
(lab/'san_module.asc').write_text(prefix+mod+suffix)
assert mod in (lab/'san_module.asc').read_text()
oldmod=extract('// BMMS1230_BEGIN','// BMMS1230_END')+'// BMMS1230_END'
planners=extract('// Closed-form peak work','static inline uint64_t RingBytes(const Plan& p)')
oldprefix=prefix.replace('static inline uint64_t RingBytes',planners+'static inline uint64_t RingBytes',1)
(lab/'san_baseline.asc').write_text(oldprefix+oldmod+suffix.replace('bmms12opt::TryLaunch','bmms1230::TryLaunch'))
p=lab/'CMakeLists.txt';s=p.read_text()
if 'sanitize_r2' not in s:
    s+='''
add_executable(sanitize_r2 main.asc)
target_compile_definitions(sanitize_r2 PRIVATE BMMS_KERNEL_HEADER="san_module.asc" BMMS_VARIANT="r2_sanitize_module")
target_link_libraries(sanitize_r2 PRIVATE tiling_api register platform unified_dlog dl m graph_base)
target_compile_options(sanitize_r2 PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=dav-2201> $<$<COMPILE_LANGUAGE:ASC>:--cce-enable-sanitizer> $<$<COMPILE_LANGUAGE:ASC>:-gline-tables-only>)
''';p.write_text(s)
if 'sanitize_r1' not in s:
    s+='''
add_executable(sanitize_r1 main.asc)
target_compile_definitions(sanitize_r1 PRIVATE BMMS_KERNEL_HEADER="san_baseline.asc" BMMS_VARIANT="r1_sanitize_r30_module")
target_link_libraries(sanitize_r1 PRIVATE tiling_api register platform unified_dlog dl m graph_base)
target_compile_options(sanitize_r1 PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=dav-2201> $<$<COMPILE_LANGUAGE:ASC>:--cce-enable-sanitizer> $<$<COMPILE_LANGUAGE:ASC>:-gline-tables-only>)
''';p.write_text(s)
print('Focused module is text-identical; only host dependencies are minimized.')

from pathlib import Path
import json,hashlib
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V12';lab=root/'V12_npu_lab/small_20261001'
base=(v/'v12_r71_small_cases_guarded.asc').read_bytes().decode();a=base.index('// BMMS1269_BEGIN');b=base.index('// BMMS1269_END',a)+len('// BMMS1269_END');mod=base[a:b]
mod=mod.replace('constexpr int kp=K<=32?32:K<=64?64:128;','constexpr int kp=K<=32?32:K<=64?64:128;\n    constexpr int IP=(K+63)/64*64; // full index-vector storage for Gather')
mod=mod.replace('pipe.InitBuffer(indices,2*kp*4);','pipe.InitBuffer(indices,2*IP*4);')
mod=mod.replace('auto ia=indices.Get<int32_t>(),ib=ia[kp];','''auto ia=indices.Get<int32_t>(),ib=ia[IP];
    // Initialize full index vectors. Unused Gather lanes safely address offset 0,
    // never a neighbouring packed buffer or an uninitialized index tail.
    AscendC::Duplicate(ia,int32_t(0),2*IP);
    AscendC::PipeBarrier<PIPE_V>();''')
mod=mod.replace('int32_t((TA?M:1)*4),K);','int32_t((TA?M:1)*4),IP);')
mod=mod.replace('int32_t((TB?1:N)*4),K);','int32_t((TB?1:N)*4),IP);')
old='''        AscendC::DataCopyPad(gy[batch],out,cp);oq.FreeTensor(out);iq.FreeTensor(in);
    }
}'''
new='''        AscendC::DataCopyPad(gy[batch],out,cp);oq.FreeTensor(out);iq.FreeTensor(in);
    }
    AscendC::ResetMask();
}'''
assert mod.count(old)==1;mod=mod.replace(old,new)
src=base[:a]+mod+base[b:];name='v12_r72_small_cases_index_padded.asc';assert not (v/name).exists()
for path in (v/name,lab/'r72.asc'):path.write_bytes(src.encode())
(lab/'r72_module.asc').write_bytes(mod.encode())
# Instrument only the exact new module so irrelevant historical kernels do not
# dominate build time or contaminate the new-path sanitizer results.
prefix='''#include "kernel_operator.h"
#include "acl/acl.h"
using namespace AscendC;
namespace bmmmaxsum_v43 { static inline bool UseTiny(int M,int N,int K){return int64_t(M)*N<=16&&K<=1024&&int64_t(M)*N*K<=8192;} }
namespace bmms71 { static inline bool UseResident(int M,int N,int K){return M<=32&&N<=64&&K<=128&&M*N<=256&&int64_t(M)*N*K<=16384&&(M+N)*K<=8192;} }
namespace bmms83 { __aicore__ inline int MinI(int a,int b){return a<b?a:b;} }
namespace bmms52 { static inline bool Eligible(int B,int M,int N,int K){return B==1&&M==1&&N==1&&K>=32&&K<=128&&K%8==0;} }
'''
suffix='''
extern "C" void run_kernel(GM_ADDR a,const TensorGroupInfo& ia,GM_ADDR b,const TensorGroupInfo& ib,GM_ADDR y,const TensorGroupInfo& iy,int64_t availableCoreNum,aclrtStream stream,bool ta,bool tb){
 const auto& x=ia.tensors[0];const auto& z=ib.tensors[0];
 const int B=x.shape[0],M=x.shape[ta?2:1],K=x.shape[ta?1:2],N=z.shape[tb?1:2];
 const int cores=availableCoreNum>0&&availableCoreNum<=64?int(availableCoreNum):1;
 if(!bmms1269::TryLaunch(a,b,y,B,M,N,K,x.dtype,ta,tb,cores,stream))std::abort();
}
'''
(lab/'r72_san_module.asc').write_bytes((prefix+mod+suffix).encode())
meta=dict(version='v12_r72',parent='v12_baseline_r41.asc',derived_from='v12_r71_small_cases_guarded.asc',sha256=hashlib.sha256(src.encode()).hexdigest(),status='pending validation',
 change='Correctness hardening: full-vector index storage, zero tail initialization, full-vector index scaling, restore mask; r71 route unchanged.',module_sha256=hashlib.sha256(mod.encode()).hexdigest(),sanitizer_module_identical=True)
(v/'v12_r72_manifest.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta,indent=2))

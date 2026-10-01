from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1];H=ROOT/'V12_npu_lab/harness'
e=(H/'event_bench_r09.asc').read_text()
a=e.index('    auto ring=');z=e.index('#define DISPATCH',a)
e=e[:a]+'''#define CALL(NAME) NAME<<<p.blocks,nullptr,stream>>>(reinterpret_cast<uint8_t*>(a),reinterpret_cast<uint8_t*>(b),reinterpret_cast<uint8_t*>(y),reinterpret_cast<uint8_t*>(ws),p)
'''+e[z:]
e=e.replace('bmms11r2::Plan','bmms23::Plan').replace('DISPATCH(bmms1209)','DISPATCH(bmms1210)').replace('DISPATCH(bmms49)','DISPATCH(bmms23)')
e=e.replace('(bmms83::NativeEligible(M,N,K)&&bmms1209::Select(bmms83::MakeNative(B,M,N,K,cores)))','bmms1210::Eligible(B,M,N,K,dt,cores)')
e=e.replace('bmms83::MakeNative(B,M,N,K,cores)','bmms23::MakePlan(B,M,N,K,cores)')
e=e.replace('(bmms83::NativeRingBytes(p)+bmms83::NativePartialBytes(p))','bmms23::WorkspaceBytes(p)').replace('candidate?"r09"','candidate?"r10"')
(H/'event_bench_r10.asc').write_text(e)
c=H/'CMakeLists.txt';s=c.read_text()
if 'event_bench_r10' not in s:
    s+='''
add_executable(event_bench_r10 event_bench_r10.asc)
target_compile_definitions(event_bench_r10 PRIVATE BMMS_KERNEL_HEADER="r10.asc" BMMS_VARIANT="r10")
target_link_libraries(event_bench_r10 PRIVATE tiling_api register platform unified_dlog dl m graph_base)
target_include_directories(event_bench_r10 PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_options(event_bench_r10 PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=${NPU_ARCH}>)
'''
    c.write_text(s)
# Exhaust all admitted M,N,K with every supported core count. Resource and
# partition bounds are independent of dtype/transposition (both are 16 bit).
count=0;max_l1=max_a2=max_b2=0
for cores in range(1,65):
 for M in range(16,65,16):
  for N in range(16,129,16):
   if M*N>4096:continue
   for K in range(4096,8193,32):
    cap=min(16,cores,K//512);S=1
    while S*2<=cap:S*=2
    if S<8:continue
    ends=[(ks*(K//32)//S)*32 for ks in range(S+1)]
    assert ends[0]==0 and ends[-1]==K
    step=min(512,(min(32768//M,32768//N)//32)*32)
    assert step>0 and M*step*2<=65536 and N*step*2<=65536
    for ks in range(S):
     kr=ends[ks+1]-ends[ks];assert 0<kr<=1024 and kr%32==0
     assert (M+N)*kr*2<=327680
     for kk in range(0,kr,step):
      kc=min(step,kr-kk)
      # Last 16x16 source block copied by each LoadData2D traversal.
      for ta in [0,1]:
       for i in range(M//16):
        off=i*kr*16+kk*16 if ta else i*256+kk*M
        end=off+(kc//16-1)*(1 if ta else M//16)*256+256
        assert end<=M*kr
      for tb in [0,1]:
       for j in range(kc//16):
        off=(kk//16+j)*N*16 if tb else (kk//16+j)*256
        end=off+(N//16-1)*(1 if tb else kr//16)*256+256
        assert end<=N*kr
     max_l1=max(max_l1,(M+N)*kr*2)
    max_a2=max(max_a2,M*step*2);max_b2=max(max_b2,N*step*2);count+=1
report=dict(plans=count,L1_max_bytes=max_l1,L0A_max_bytes=max_a2,L0B_max_bytes=max_b2,
            partitions_and_copy_source_bounds=True,original_consumer=True)
(ROOT/'V12_impl_r10/HOST_CHECKS.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))

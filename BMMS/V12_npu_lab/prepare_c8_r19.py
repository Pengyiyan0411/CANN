from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parents[1];H=R/'V12_npu_lab/harness';O=R/'BMMS_V12'
src=(O/'v12_r18_case8_adaptive_nz.asc').read_bytes()
a=src.index(b'// BMMS1218_BEGIN');b=src.index(b'// BMMS1218_END\n\n',a)+len(b'// BMMS1218_END\n\n')
mod=src[a:b].decode().replace('1218','1219')
old='AscendC::Max(merged,merged,tmp,p.M);bmms71::Fence<AscendC::HardEvent::V_MTE2>(*pipe_);'
new='''// Explicit normal-mask mode makes full repeats and the final tail
                // bounds visible instead of relying on the count-mask overload.
                AscendC::BinaryRepeatParams mergeRepeat{1,1,1,8,8,8};
                const int full=p.M/64,tail=p.M%64;
                if(full)AscendC::Max(merged,merged,tmp,uint64_t(64),uint8_t(full),mergeRepeat);
                if(tail)AscendC::Max(merged[full*64],merged[full*64],tmp[full*64],uint64_t(tail),uint8_t(1),mergeRepeat);
                bmms71::Fence<AscendC::HardEvent::V_MTE2>(*pipe_);'''
assert mod.count(old)==1
mod=mod.replace(old,new)
data=src[:a]+mod.encode()+src[b:]
data=data.replace(b'if(bmms1218::TryLaunch',b'if(bmms1219::TryLaunch',1)
base=(O/'v12_baseline_r12.asc').read_bytes()
rec=data.replace(mod.encode(),b'',1)
hook=next(x for x in rec.splitlines(keepends=True) if b'if(bmms1219::TryLaunch' in x)
assert rec.replace(hook,b'',1)==base
name='v12_r19_case8_nz_explicit_tail.asc'
(O/name).write_bytes(data);(H/'r19.asc').write_bytes(data)
j=dict(candidate=name,parent='v12_baseline_r12.asc',parent_sha256=hashlib.sha256(base).hexdigest(),sha256=hashlib.sha256(data).hexdigest(),parent_recovered_byte_for_byte=True,status='validation pending',difference_from_r18='explicit normal-mask full repeats plus tail for final row-Max merge only')
(O/'v12_r19_manifest.json').write_text(json.dumps(j,indent=2)+'\n')
e=(H/'event_bench_r18.asc').read_text().replace('1218','1219').replace('"r18"','"r19"');(H/'event_bench_r19.asc').write_text(e,newline='\n')
c=H/'CMakeLists.txt';s=c.read_text()
if 'add_executable(bench_r19' not in s:
 s+='''
add_executable(bench_r19 main.asc)
add_executable(event_bench_r19 event_bench_r19.asc)
add_executable(sanitize_r19 main.asc)
foreach(t IN ITEMS bench_r19 event_bench_r19 sanitize_r19)
  target_compile_definitions(${t} PRIVATE BMMS_KERNEL_HEADER="r19.asc" BMMS_VARIANT="r19")
  target_link_libraries(${t} PRIVATE tiling_api register platform unified_dlog dl m graph_base)
  target_include_directories(${t} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
  target_compile_options(${t} PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=${NPU_ARCH}>)
endforeach()
target_compile_options(sanitize_r19 PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--cce-enable-sanitizer> $<$<COMPILE_LANGUAGE:ASC>:-gline-tables-only>)
add_custom_target(c8_r19_build DEPENDS bench_r19 event_bench_r19 sanitize_r19)
''';c.write_text(s,newline='\n')
print(json.dumps(j))

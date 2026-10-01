from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V12';lab=root/'V12_npu_lab/small_20261001';lab.mkdir(exist_ok=True)
out=root/'V12_npu_lab/results/small_20261001';out.mkdir(exist_ok=True)
base=(v/'v12_baseline_r41.asc').read_bytes().decode()
a=base.index('// BMMS52_BEGIN');b=base.index('// BMMS52_END',a)+len('// BMMS52_END')
mod=base[a:b].replace('bmms52','bmms1268').replace('BMMS52','BMMS1268')
old='    AscendC::ReduceSum(out,fa,scratch.Get<float>(),K);'
assert mod.count(old)==1
mod=mod.replace(old,'''    // Keep the same 64-element partial sums, but leave the final result on Vector.
    // The generic ReduceSum implementation also introduces V->S->V/MTE3 handshakes.
    if constexpr(K<=64){
        AscendC::WholeReduceSum(out,fa,K,1,1,1,8);
    }else{
        auto sums=scratch.Get<float>();
        AscendC::WholeReduceSum(sums,fa,64,1,1,1,8);
        AscendC::WholeReduceSum(sums[8],fa[64],K-64,1,1,1,8);
        AscendC::PipeBarrier<PIPE_V>();
        AscendC::Add(out,sums,sums[8],1);
    }''')
hook='    if(bmms1268::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,stream))return;\n'
pos=base.index('extern "C" void run_kernel(');src=base[:pos]+mod+'\n\n'+base[pos:]
pos=src.index('    if(bmms1203::TryLaunch');src=src[:pos]+hook+src[pos:]
assert src.replace(mod+'\n\n','',1).replace(hook,'',1)==base
name='v12_r68_short_dot_vector_reduce.asc';assert not (v/name).exists()
for path in (v/name,lab/'r68.asc'):path.write_bytes(src.encode())
(lab/'r68_module.asc').write_bytes(mod.encode());(lab/'r41.asc').write_bytes(base.encode())
meta=dict(version='v12_r68',parent='v12_baseline_r41.asc',sha256=hashlib.sha256(src.encode()).hexdigest(),
          status='pending NPU build/validation',parent_byte_recovery=True,new_device_entries=26,
          change='Short dot: explicit WholeReduceSum and two-part Add; retain original TQue/cast/mul/K domain')
(v/'v12_r68_manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
main=(root/'V12_npu_lab/rethink_20261001/main.asc').read_text()
# Annotate this study's actual metadata domains instead of the old Case12 label.
l=main.index('        bool target=false;');r=main.index('        double wall=',l)
main=main[:l]+'''        const bool target=bmms52::Eligible(B,M,N,K);
        std::printf("CASE %d B=%lld M=%lld N=%lld K=%lld dtype=%d ta=%d tb=%d\\n",id,(long long)B,(long long)M,(long long)N,(long long)K,dt,ta,tb);
'''+main[r:]
main=main.replace('case12_k1_guard','short_dot_domain')
(lab/'main.asc').write_text(main,newline='\n')
(lab/'run_screen.py').write_bytes((root/'V12_npu_lab/rethink_20261001/run_screen.py').read_bytes())
(lab/'CMakeLists.txt').write_text('''cmake_minimum_required(VERSION 3.16)
find_package(ASC REQUIRED)
project(bmms_small LANGUAGES ASC CXX)
set(CMAKE_CXX_STANDARD 17)
foreach(v r68)
 add_executable(bench_${v} main.asc)
 target_compile_definitions(bench_${v} PRIVATE BMMS_KERNEL_HEADER="${v}.asc" BMMS_VARIANT="${v}")
 target_link_libraries(bench_${v} PRIVATE tiling_api register platform unified_dlog dl m graph_base)
 target_compile_options(bench_${v} PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=dav-2201>)
endforeach()
''',newline='\n')
(out/'PLAN.md').write_text('''# Case1–4 短路径实验计划

2026-10-01，基线r41。隐藏Case1工作画像B=M=N=1，K32..128；2–4为M/N2..16、短K，单/多batch。精确shape、dtype、layout未确认。

先单独验证短点积去除通用ReduceSum的scalar收尾（r68），再单独验证小矩阵批量向量归约（r69）。不重用无收益R51，不影响原Native Case5。各候选直接基于r41，最多三轮。

用例在测量前冻结：全部短K、两dtype、四布局、奇数M/N、多batch跨40AIV边界、负值/零/相消/尺度变化；参考使用量化输入的CPU FP64。每次输出NaN毒化，逐配置对比。单点积要记录绝对ns与窗口波动，避免把1us量级的离群采样当收益。

先精度，后串行ABBA轻量msprof；主要筛选用两个窗口，每窗口80次丢20次，入围做独立形状/种子留出及instrumented检查。预先标准：中位≥5%，窗口方向一致，无未解释>3%稳定退化。未知精确Judge输入不能伪装成实测Case1–4。

本项目为单ASC直接ACL ABI，不是ascend-kernel Python扩展；沿用已验证C ABI/msprof双路径对照，标杆为冻结r41本机运行，CPU FP64只作精度参考。公开榜单隐藏输入成绩不用于本机加速比。CANN9实际头文件决定API细节。
''',encoding='utf-8')
print(json.dumps(meta))

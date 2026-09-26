"""Record compile failure without inventing a compiler error, then document R22."""
from pathlib import Path
import importlib.util,json,subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
PREVIOUS='c0a34e5828260c8311e53cec5b9dfbee8e7dab06'
spec=importlib.util.spec_from_file_location('builder',HERE/'build.py');build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)

def main():
    build.verify();checks=json.loads((HERE/'CHECKS.json').read_text(encoding='utf-8'))
    dispatch=json.loads((HERE/'DISPATCH_CHECKS.json').read_text(encoding='utf-8'))
    for rel,digest in dispatch['sources'].items():assert build.sha(ROOT/rel)==digest
    audit='BatchMatmulMaxSum_当前审计报告_2026-09-26.md'
    frozen=subprocess.check_output(['git','show',PREVIOUS+':BMMS/'+audit],cwd=ROOT/'CANN_archive')
    snapshot=ROOT/'audit_current/AUDIT_R20_R21_DELIVERY.md'
    if snapshot.exists():assert snapshot.read_bytes()==frozen
    else:snapshot.write_bytes(frozen)
    results=ROOT/'V11_results/2026-09-27_r20_compile_failed';results.mkdir(exist_ok=True)
    evidence={'source':'user report','version':'R20','status':'compile_failed','compile_log_available':False,
              'first_error_known':False,'root_cause_confirmed':False,'timings_available':False,
              'source_risk':'host-only UseWideN called from device NativeEntry; not a confirmed diagnosis of the platform error',
              'R21_platform_status_known':False,'next_candidate':'R22_SHAPE_SWITCH','baseline':'R14',
              'user_requested':'switch strategies using specific input metadata, not a broad Native producer replacement'}
    build.write(results/'RESULTS.json',json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    build.write(results/'AUDIT.md','''# R20 编译失败反馈

用户确认 R20 未编译通过，随后确认没有编译日志。记录为编译阶段失败；
首条错误、编译器版本和准确根因未知，不记录运行时间或 Pass 数。
源码中的 host-only UseWideN 被设备 NativeEntry 调用是一个风险点，尚不能证明就是平台错误。
R21 状态未收到。本轮按用户要求回到 R14，实现按具体元数据选择不同固定内核的 R22。
R20/R21 旧交付内容保持冻结；其“待测”文字表示当时的历史状态。
''')
    rules='''| 输入条件（原 Native 域内） | R22 内核 |
|---|---|
| N=16/32、M>32；K=32/64/128 | 64×32 窄列 |
| M=16/32、N≥256 且为 256 倍数；K=32/64 | 32×256 宽列 |
| M/N 均≥128 且均为 128 倍数；K=32/64/128 | 128×128 稠密 |
| 未命中，或新计划减少可用核组 | 原 R14 |
'''
    r=checks['runs']['R22'];base=checks['runs']['R14']
    work='''| 合成控制例（B1、1 核组） | 指标 | R14 → R22 |
|---|---|---|
'''
    for key,label,metric in [('M256_N16_K128','M256/N16/K128','duplicate_elements'),('M32_N512_K64','M32/N512/K64','mmads'),('M256_N512_K64','M256/N512/K64','mmads')]:
        a,b=base['shape_fixtures'][key],r['shape_fixtures'][key]
        work+=f'| {label} | {"填充元素数" if metric=="duplicate_elements" else "MMAD / Fixpipe 调用数"} | {a[metric]} → {b[metric]} |\n'
    readme=f'''# R22_SHAPE_SWITCH

提交 `R22_SHAPE_SWITCH.asc`，完整替换上一份源码；单文件内部自动分派，不需要手动选版本。
`R14_CONTROL.asc` 与已通过平台的原 R14 字节一致，供相邻对照。

{rules}
各分支再按 dtype、TA/TB、K 选择固定入口，共 64 个绑定；B 和核数参与分核与回退。
全部选择发生在 host，设备入口具有固定片上尺寸。

{work}
上表是源码模型的逻辑工作量，不是平台耗时或 Case 5 的真实形状。
Case 5 已定位 Native，但精确 M/N/K 未知，新策略未必命中它。

本地每版 {r['source_runs']} 次普通源码模型运行，{r['repeat_pairs']} 次重复核对，R22 与 R14 输出逐位一致。
三种新策略分别运行 {r['shape_route_runs'][1]} / {r['shape_route_runs'][2]} / {r['shape_route_runs'][3]} 次；
64 个入口绑定、2016 个元数据计划与三项故障注入检查通过。
没有本地 CANN 编译或 NPU 运行，目标编译与性能须由提交确认；原有 3 项极端数值限制保留。

R20 记录为编译失败，无日志、根因未确认，本版从 R14 独立生成。
请先看全部 15 点是否 Pass，再比较 Case 5 和其他 Native 点。
微小差异用相邻 R14 重复提交判断；保留完整结果及当轮标杆，避免把测评波动当作收益。
'''
    build.write(build.OUT/'README.md',readme)
    build.write(ROOT/audit,f'''# BatchMatmulMaxSum 当前审计：R20 编译失败，R14 基线重做 R22

2026-09-27。R14 仍为用户指定基线；已有 15/15 Pass。R20 编译失败，用户没有日志，
准确根因未知；R21 平台状态未收到。R22 已完成按输入元数据选择固定内核，尚待平台提交。

## 问题与修正

上一轮 R20 只按 N 分片长度选择宽 N 生产者，R21 则替换整个 Native 生产者，
没有满足本轮要求的具体形状到策略映射。R22 从 R14 独立生成，host 分开选择
ShortN、ShortM、Dense 内核，再按 K/dtype/布局选择固定入口。
未命中的形状和可能损失可用核组的候选走原 R14。

R20 的 UseWideN 缺少设备标注却从 NativeEntry 调用，是源码风险；
无日志时不能把它写成已确认的编译失败根因。R22 设备入口不调用 host selector，
每个入口只使用一组固定资源布局。
[编译失败反馈](V11_results/2026-09-27_r20_compile_failed/AUDIT.md)。

## Case 5 依据与边界

用户提供 P01/R06 stress 7.71、P02/R03 stress 7.58、P03/Native stress 14.11、
P04/Tree stress 7.20 μs，并说明 P03 只改 Native plan。继续以 Native fixed-small-K
为已定位工作路径：M/N≥16 且 16 对齐、K32/64/128，排除 Tiny/Resident。
确切 B/M/N/K、dtype、TA/TB 未知。新 probe 源码/hash 和全点重复样本未收到；
仓库旧 P03_TREE_OFF 不等同于这个 Native stress。
[诊断记录](V11_results/2026-09-27_native_case5/AUDIT.md)。

## 具体实现

{rules}
ShortN 缩小存储和向量处理宽度；ShortM 合并 N tile；Dense 增加 M 高度以复用 B。
三条路径都同步修改生产者、消费者和 workspace；保留全 K 的 FP32 累加、行 max 和 M 求和。
R14 原源码除了新增片段、一个 host 调用和首行版本注释，可逐字还原。
[完整条件、容量、代价和 API 依据](V11_shape_dispatch/DESIGN.md)。

{work}
逻辑工作量减少不等于设备提速。ShortM 的向量填充可能增加，Dense 的 L0C 和 ring 更大，
最终盈亏待平台。也不能保证未知形状的 Case 5 会进入新分支。

## 已完成验证

每版 {r['source_runs']} 次普通源码模型运行、{r['repeat_pairs']} 次重复核对，与 R14 普通输出逐位一致。
R22 的 ShortN/ShortM/Dense 实际源码分别执行 {r['shape_route_runs'][1]}/{r['shape_route_runs'][2]}/{r['shape_route_runs'][3]} 次，
Native 回退执行 {r['shape_route_runs'][0]} 次。每版 {r['native_work_checks']} 次 Native 独立流量公式核对。
覆盖 FP16/BF16、四种布局、K32/64/128、尾块/尾 packet、多 batch/pM/pN、负值和零。

真实 host/入口记录桩：{dispatch['actual_host_launch_checks']} 次检查覆盖全部 64 个新入口和
{dispatch['no_launch_fallback_checks']} 次不分配/不发射回退；2016 个元数据计划中验证了
{dispatch['occupancy_fallbacks']} 次核组减少回退。错误归约步长、遗漏宽列上半区和错误 dtype
入口三项故障注入全部被拒绝。
[源码检查](V11_shape_dispatch/CHECKS.json) / [分派检查](V11_shape_dispatch/DISPATCH_CHECKS.json)。

这些是本地 CPU 模型和记录桩验证，不能代替 CANN 编译、异步 NPU 行为和设备计时。
既有 3 项极端数值限制未改变。没有填写 R22 的平台 Pass、分数或预测速度。

## 当前交付与下一步

只需提交 [R22 单文件](BMMS_V11_R22/R22_SHAPE_SWITCH.asc)。
[提交包](BMMS_V11_R22_提交包.zip) 附带原 R14 控制与说明。
先验收全部 15 点，再用相邻 R14 完整结果判断收益，微小差异重复确认。
R20/R21 旧交付冻结在[历史审计](audit_current/AUDIT_R20_R21_DELIVERY.md)，不覆盖旧源码或 ZIP。
归档分支：[CANN/v11](https://github.com/Pengyiyan0411/CANN/tree/v11/BMMS)。
''')
    links=[('R22 单文件','BMMS_V11_R22/R22_SHAPE_SWITCH.asc'),('提交包','BMMS_V11_R22_提交包.zip'),
           ('使用说明','BMMS_V11_R22/README.md'),('当前审计',audit),('分派设计','V11_shape_dispatch/DESIGN.md'),
           ('源码检查','V11_shape_dispatch/CHECKS.json'),('分派检查','V11_shape_dispatch/DISPATCH_CHECKS.json'),
           ('R20 失败反馈','V11_results/2026-09-27_r20_compile_failed/AUDIT.md'),
           ('上轮交付快照','audit_current/AUDIT_R20_R21_DELIVERY.md')]
    index='''# BatchMatmulMaxSum：R14 基线，R22 按元数据选择固定内核

R20 平台编译失败且没有日志。R22 从 R14 重做：短 N 窄列、短 M 宽列、对齐稠密高 M 块；
host 根据真实形状、K、dtype、布局和并行度选择内核。单文件提交，未覆盖组合保留 R14。
本地源码模型检查通过，CANN 编译/NPU 性能待提交，R14 仍是已验证基线。

'''+''.join(f'- [{label}]({path})\n' for label,path in links)+'''
```powershell
python V11_shape_dispatch/build.py
python V11_shape_dispatch/run_checks.py
python V11_shape_dispatch/check_dispatch.py
python V11_shape_dispatch/update_docs.py
python V11_shape_dispatch/package.py
```

旧源码、结果和提交包保持冻结。审计快照生成需要 CANN_archive 中的历史 commit。
'''
    build.write(ROOT/'README.md',index);cann=index
    for _,path in links:cann=cann.replace(']('+path+')','](BMMS/'+path+')')
    build.write(HERE/'CANN_README.md',cann.replace('```powershell\n','```powershell\ncd BMMS\n'))
    status=json.loads((ROOT/'ARCHIVE_STATUS.json').read_text(encoding='utf-8'))
    assert status['working_baseline']=='R14'
    status.pop('R20_R21_platform_results_received',None)
    status.update(R20_status='compile_failed',R20_compile_log_available=False,R20_root_cause_confirmed=False,
                  R21_platform_result_received=False,R22_platform_result_received=False,
                  R22_source_sha256=build.sha(build.OUT/(build.NAME+'.asc')),R22_cpu_ordinary_runs=r['source_runs'],
                  R22_cpu_repeat_checks=r['repeat_pairs'],R22_cpu_outputs_equal_R14=True,
                  R22_cann_compiled_locally=False,R22_npu_tested_locally=False,
                  latest_feedback='R20 failed compilation; no log. User requests metadata-specific strategy switching based on R14.',
                  next_action='Submit R22_SHAPE_SWITCH.asc; check all cases and compare with adjacent R14 controls.')
    build.write(ROOT/'ARCHIVE_STATUS.json',json.dumps(status,ensure_ascii=False,indent=2)+'\n')
    print('R20 failure recorded; R22 usage, audit and history snapshot written.')
if __name__=='__main__':main()

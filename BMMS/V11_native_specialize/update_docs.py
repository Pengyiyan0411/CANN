"""Record user-provided Case 5 evidence separately from untested candidates."""
from pathlib import Path
import importlib.util,json,subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
PREVIOUS='225bb791620752f8f7df192e57d849e91f1a8f61'
spec=importlib.util.spec_from_file_location('builder',HERE/'build.py');build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)

def main():
    build.verify();checks=json.loads((HERE/'CHECKS.json').read_text(encoding='utf-8'))
    dispatch=json.loads((HERE/'DISPATCH_CHECKS.json').read_text(encoding='utf-8'))
    for p,digest in dispatch['sources'].items():assert build.sha(ROOT/p)==digest
    baseline=json.loads((ROOT/'ARCHIVE_STATUS.json').read_text(encoding='utf-8'))
    assert baseline['working_baseline']=='R14'
    audit='BatchMatmulMaxSum_当前审计报告_2026-09-26.md'
    frozen=subprocess.check_output(['git','show',PREVIOUS+':BMMS/'+audit],cwd=ROOT/'CANN_archive')
    snapshot=ROOT/'audit_current/AUDIT_R17_R18_R19_DELIVERY.md'
    if snapshot.exists():assert snapshot.read_bytes()==frozen
    else:snapshot.write_bytes(frozen)
    results=ROOT/'V11_results/2026-09-27_native_case5';results.mkdir(exist_ok=True)
    rows=[{'probe':'P01','user_label':'R06 stress','case':5,'time_us':7.71},
          {'probe':'P02','user_label':'R03 stress','case':5,'time_us':7.58},
          {'probe':'P03','user_label':'Native stress','case':5,'time_us':14.11},
          {'probe':'P04','user_label':'Tree stress','case':5,'time_us':7.20}]
    evidence={'date':'2026-09-27','source':'user message with timings and code-scope explanation',
        'rows':rows,'native_to_other_probes_median_ratio':14.11/7.58,
        'working_diagnosis':'R14 Native fixed-small-K route; M,N >=16 and multiples of16; K in {32,64,128}; excludes Tiny and Resident',
        'unknown':['B','exact K','exact M/N','TA/TB','dtype'],
        'probe_source_hashes_available':False,'full_15_case_probe_results_available':False,
        'old_P03_TREE_OFF_is_not_this_probe':True,
        'user_post_R14_feedback':'后面几个版本都没什么收益',
        'post_R14_per_version_pass_status_or_timings_available':False,
        'scores_not_recomputed_from_partial_probe_data':True,
        'new_candidate_platform_results_available':False}
    build.write(results/'RESULTS.json',json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    build.write(results/'case5.csv','probe,user_label,case,time_us\n'+''.join(f'{r["probe"]},{r["user_label"]},5,{r["time_us"]:.2f}\n' for r in rows))
    build.write(results/'AUDIT.md','''# Case 5 Native 诊断证据

用户本轮给出 P01/R06 stress 7.71、P02/R03 stress 7.58、P03/Native stress 14.11、
P04/Tree stress 7.20 μs，并说明 P03 只改变顶层 Native 执行计划。
据此以 Native fixed-small-K 为后续优化路径；与其余三项中位数相比约 1.86 倍。
没有重新把它当成未知路由，也不把其他 probe 的阴性反应当成独立排除证据。

M/N≥16、16 对齐，K∈{32,64,128}，排除 Tiny/Resident。具体形状、布局和 dtype 未知。
新 probe 完整源码/hash、全部 15 点及重复原始样本未收到；这是用户提供的诊断记录。
仓库旧 P03_TREE_OFF 属于另一套 probe，不能混用。本记录不反推完整分数。

用户定性表示 R14 后几个版本无明显收益，未提供逐版数据或通过状态；保留 R14 为基线。
R20/R21 是本轮新交付的独立候选，还没有平台结果。
''')
    runs=checks['runs'];n=runs['R14']['source_runs'];pairs=runs['R14']['repeat_pairs']
    a,b,c=[runs[v]['native_fixtures']['K128_N1024'] for v in ['R14','R20','R21']]
    short=[runs[v]['native_fixtures']['K128_N16']['b0_calls'] for v in ['R14','R21']]
    table=f'''| 控制例 B1/M256/N1024/K128/1核组 | R14 | R20 | R21 |
|---|---:|---:|---:|
| MMAD 调用 | {a['mmads']} | {b['mmads']} | {c['mmads']} |
| A→L0A 字节 | {a['a0_bytes']} | {b['a0_bytes']} | {c['a0_bytes']} |
| LoadData 调用 | {a['l0_calls']} | {b['l0_calls']} | {c['l0_calls']} |
| B→L0B 字节 | {a['b0_bytes']} | {b['b0_bytes']} | {c['b0_bytes']} |
| Fixpipe 调用 | {a['fixpipes']} | {b['fixpipes']} | {c['fixpipes']} |
'''
    readme=f'''# R20 / R21：R14 Native small-K 专项候选

建议先提交 `R21_NATIVE_L0_REUSE.asc`，再单独提交 `R20_NATIVE_WIDE_N.asc`。
两者均独立基于 R14，分别完整替换原提交源码；不叠加、不拼接。
`R14_CONTROL.asc` 与原 R14 字节完全一致，供相邻复测。

- R21：A 在适合复用的任务中驻留 L0A；短轴 LoadData 打包也覆盖窄 N。
- R20：两块 N 微块合为一次完整 K MMAD，仍按原 packet 输出；每个 N 分片至少两块才启用。
- host 分核、路由域、FP32 中间结果和 AIV 归约均保持 R14。

{table}
另一个 M256/N16/K128 控制例中，R21 的 B LoadData 调用 {short[0]}→{short[1]}，字节数相同。
这些是合成输入上的源码逻辑计数，不是 Case 5 的形状或设备加速测量。

本地每版 {n} 次普通源码模型运行、{pairs} 次重复核对，三版普通输出逐位一致；
两类故障注入被拒绝。3 项既有极端数值限制未修复。没有本地 CANN 编译或 NPU 测试。

重点记录 Case 5，同时检查全部 15 点 Pass 和其他点退化。若只有小幅变化，在相邻 R14
控制下重复提交再判断，保留每次完整结果与当轮 T，不取各版最短值拼接。
R20 没变化可能是保守启用条件未命中，不足以否定 Native 定位。
源码 hash 见 MANIFEST.json；离线检查与限制见 CPU_CHECKS.json。
'''
    build.write(build.OUT/'README.md',readme)
    audit_text=f'''# BatchMatmulMaxSum 当前审计：R14 基线，Native Case 5 专项 R20/R21

2026-09-27。用户确认 R14 为基线，并定性反馈后续几个版本没有明显收益。
本轮围绕 P03 强阳性响应定位的 Native small-K 路径实现两个独立候选，尚无新平台成绩。

## 当前证据

R14 已有 15/15 Pass，历史最新一组 T 复算 37.259712；该 T 不是当前实时排行榜快照。
R14 Case 5 为 7.20 μs。用户给出的本轮四个 probe 对 Case 5 分别为 7.71、7.58、14.11、7.20 μs，
其中 P03 只改变 Native plan。该干预支持将优化域锁定为 K32/64/128、M/N 至少 16 且 16 对齐的
Native 路径，semantic family 是 ShortM、ShortN、Dense small-K 三者之一。

接受该定位继续实现，不按绝对耗时猜路由。B、精确 M/N/K、dtype、TA/TB 未知。
新 probe 源码/hash 和重复全点结果未收到；仓库旧 P03_TREE_OFF 不是这里的 Native stress。
[本轮证据记录](V11_results/2026-09-27_native_case5/AUDIT.md)。
“R14 后版本无明显收益”仅按定性反馈记录，没有补写 R15–R19 的分数、Pass 数或具体退化点。

## 本轮实现

| 版本 | 独立修改 | 启用范围 |
|---|---|---|
| R21_NATIVE_L0_REUSE | 复用 L0A；LoadData 选择较短循环轴 | 原 Native 域；A 驻留仅每个 N 分片至少两块 |
| R20_NATIVE_WIDE_N | 64×256 完整 K MMAD，拆回原 64×128 输出 | 原 Native 域内，每个 N 分片至少两块 |

R05 的延迟 Max 归约已试过，故本轮转向 AIC 指令与片上搬运。
两版源码都能还原为原 R14：host 计划、分派门槛、AIV、GM workspace、packet 布局不变。
R20 单槽 L0B 配两槽 L0C，按 MMAD 序号回收 C；R21 对 A2 跨 M 段的生命周期补全事件归还。
[设计、容量及 API 依据](V11_native_specialize/DESIGN.md)。

## 离线证据

{table}
R21 在短 N 控制例中 B LoadData {short[0]}→{short[1]}。这些不是隐藏测试点，也不能换算为设备提速。
原 GM A/B 读取、C 元素覆盖、Fixpipe 输出及 READY/FREE 协议已核对保持一致。

每版 {n} 次普通运行、{pairs} 次重复核对，原有结果及新用例与 R14 逐位一致。
覆盖 3 种 K、2 种 dtype、4 种布局、尾 N、跨 AM/batch、负数/零和线程顺序变化；
每版 {runs['R14']['native_work_checks']} 次 Native 逻辑流量核对。
R20 宽 N 和 R21 A0 复用各执行 {runs['R20']['wide_route_runs']} 次。
错误 Fixpipe 源偏移和错误 A0 行偏移均被负向测试拒绝。
真实 NativeEntry 记录桩检查 {dispatch['actual_entry_checks']} 项，选择器 {dispatch['selector_checks']} 项，
原计划检查 {dispatch['actual_plan_checks']} 项。

本地没有 CANN/NPU，以上是源码模型验证。已知 3 项极端数值限制仍存在，
异步硬件行为、实际资源分配、Cube 舍入及性能必须等待提交，不能写成平台 Pass。
[检查报告](V11_native_specialize/CHECKS.json) / [入口检查](V11_native_specialize/DISPATCH_CHECKS.json)。

## 下一次提交

先 R21，后独立 R20；都与相邻 R14 控制比较，不先合并。
重点 Case 5，同时保留所有点、Pass 状态及当轮 T。小幅改善需重复，不把亚微秒差异直接认定为收益。
两项都无明显变化时，下一步用更细的元数据分组干预定位 N 分片长度或 K/布局；不是重新判断 Native。

[提交包](BMMS_V11_R20_R21_提交包.zip) / [说明](BMMS_V11_R20_R21/README.md)。
历史来源：[上轮交付审计冻结副本](audit_current/AUDIT_R17_R18_R19_DELIVERY.md)。
所有旧源码、结果、提交 ZIP 冻结，归档分支 [CANN/v11](https://github.com/Pengyiyan0411/CANN/tree/v11/BMMS)。
'''
    build.write(ROOT/audit,audit_text)
    index='''# BatchMatmulMaxSum：R14 基线，Native small-K R20/R21

本轮根据用户的 Case 5 Native-stress 响应，针对原生 K32/64/128 路径实现独立候选。
R14 仍是工作基线；R20/R21 暂无平台结果，历史后续版本无收益反馈未被写成定量成绩。

- [R20/R21 提交包](BMMS_V11_R20_R21_提交包.zip) / [使用说明](BMMS_V11_R20_R21/README.md)
- [当前审计](BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [专项设计](V11_native_specialize/DESIGN.md) / [源码检查](V11_native_specialize/CHECKS.json)
- [Case 5 诊断证据](V11_results/2026-09-27_native_case5/AUDIT.md)
- [上轮交付快照](audit_current/AUDIT_R17_R18_R19_DELIVERY.md)

先独立提交 R21（L0 搬运复用），再提交 R20（宽 N MMAD）。R14 控制源码已随包提供。
普通离线源码模型输出与 R14 一致；本地无 CANN/NPU，不宣称真实性能收益。

```powershell
python V11_native_specialize/build.py
python V11_native_specialize/run_checks.py
python V11_native_specialize/check_dispatch.py
python V11_native_specialize/update_docs.py
python V11_native_specialize/package.py
```

源码与历史记录归档：[CANN/v11](https://github.com/Pengyiyan0411/CANN/tree/v11/BMMS)。
审计快照生成依赖本地 CANN_archive 中的历史 commit。
'''
    build.write(ROOT/'README.md',index)
    # The repository README sits one level above BMMS.
    cann=index
    for label,path in [('提交包','BMMS_V11_R20_R21_提交包.zip'),('使用说明','BMMS_V11_R20_R21/README.md'),
                       ('当前审计',audit),('专项设计','V11_native_specialize/DESIGN.md'),('源码检查','V11_native_specialize/CHECKS.json'),
                       ('Case 5 诊断证据','V11_results/2026-09-27_native_case5/AUDIT.md'),('上轮交付快照','audit_current/AUDIT_R17_R18_R19_DELIVERY.md')]:
        cann=cann.replace(']('+path+')','](BMMS/'+path+')')
    cann=cann.replace('```powershell\n','```powershell\ncd BMMS\n')
    build.write(HERE/'CANN_README.md',cann)
    print('Recorded Case 5 evidence, updated audit, and wrote submission instructions.')

if __name__=='__main__':main()

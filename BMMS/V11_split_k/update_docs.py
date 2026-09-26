"""Record scoped Case15 evidence and R23 delivery, preserving the prior audit."""
from pathlib import Path
import importlib.util,json,subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
PREVIOUS='f0c559636b68c7f84ba3ac467e04292a4e6f0e04'
spec=importlib.util.spec_from_file_location('builder',HERE/'build.py');build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)

def main():
    build.verify();checks=json.loads((HERE/'CHECKS.json').read_text(encoding='utf-8'))
    dispatch=json.loads((HERE/'DISPATCH_CHECKS.json').read_text(encoding='utf-8'))
    for rel,digest in {**checks['artifacts'],**dispatch['sources']}.items():assert build.sha(ROOT/rel)==digest,rel
    audit='BatchMatmulMaxSum_当前审计报告_2026-09-26.md'
    frozen=subprocess.check_output(['git','show',PREVIOUS+':BMMS/'+audit],cwd=ROOT/'CANN_archive')
    snapshot=ROOT/'audit_current/AUDIT_R22_DELIVERY.md'
    if snapshot.exists():assert snapshot.read_bytes()==frozen
    else:snapshot.write_bytes(frozen)
    results=ROOT/'V11_results/2026-09-27_case15_long_k';results.mkdir(exist_ok=True)
    evidence={'source':'user-provided scoped-probe analysis; original new probe files/hashes not provided',
              'R22_feedback':'no useful improvement; no full result table or compile/Pass status supplied',
              'case':15,'normal_R03_us_interval':[36,38],
              'case15_probe_us':{'A01_R03_OFF':112.60,'C512':108.65,'C1024':113.67,'C2048':112.77,'C4096':112.83,'P02_R03_STRESS':37.38},
              'C_mean_us':sum([108.65,113.67,112.77,112.83])/4,
              'reported_C_predicate':'bypass R03 if K >= threshold',
              'reported_B_findings':{'M_min':16,'M_exclusive_max':128,'M_alignment':16,'N_min':16,'N_exclusive_max':256,'N_alignment':16,'B_less_than_cores':True},
              'working_K_inference':{'min':4096,'max':8192,'alignment':32},
              'unconfirmed_hypotheses':['B == 1','M <= 64','N <= 128','M*N <= 4096'],
              'case7_C_response':'user reports about 11 us, no fallback shift; supportive cross-case control',
              'reported_best_column_us':4.05,'best_column_semantics_independently_verified':False,
              'probe_sources_hash_verified':False,'complete_15_case_tables_received':False,
              'baseline':'R14','next_candidate':'R23_SPLIT_K','local_cann_or_npu_validation':False}
    build.write(results/'RESULTS.json',json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    build.write(results/'AUDIT.md','''# Case15：长 K 的作用域证据

本轮数据来自用户文本；新的 A/B/C/P02 探针源码、hash、完整 15 点表和重复原始样本未收到。
不把它们与仓库中同名旧探针自动混用。

| 用户提供的 Probe | Case15，μs |
|---|---:|
| 正常 R03 | 约 36–38 |
| A01 R03_OFF | 112.60 |
| C512 | 108.65 |
| C1024 | 113.67 |
| C2048 | 112.77 |
| C4096 | 112.83 |
| P02 R03 stress | 37.38 |

C 均值 111.98 μs。根据用户描述的条件 bypass，四个 C 都恢复到 A01 fallback 状态，
支持 K≥4096；R03 原 guard 给出 K≤8192 且 32 对齐。B 系列结论是
16≤M<128、16≤N<256，均 16 对齐，B<cores。

P02 的 null result 不能单独证明 B=1、M≤64 或 N≤128。新 G01–G04 逐一确认这些几何条件；
R23 直接支持已知完整 M/N 范围和多 batch，不等这些假说成立才可运行。
Case7 没有随 C 退化是辅助对照，原始数据不足以新增统计检验或精确形状结论。

4.05 μs 记录为用户报告的“最优用时”列，页面含义和时点未独立核验，
不由此生成预测速度、名次或新分数。
R22 的新反馈为“没用”，记为定性无收益，不填造编译状态、Pass 数或逐点耗时。
''')
    rules='''仅在 `M=16..112、N=16..240`（均 16 对齐）、`K=4096..8192`（32 对齐）、
FP16/BF16，且空间任务没有占满可用核时启用。按 B、M/N tile 数、K 和核数自动选择 2/4/8/16 个 K 分片。
未满足条件时执行原 R14。四种 TA/TB 布局都有独立入口。
'''
    readme=f'''# R23_SPLIT_K 提交说明

先提交 **R23_SPLIT_K.asc**，完整替换当前源码。它从 R14 独立生成，不继承 R22。
本轮目标是 Case15 的小输出、超长 K：多个 Cube 组各算一段 K，先合并完整 C，再做 max(N) 和 sum(M)。

{rules}
不要求 B=1、M≤64、N≤128。每个 Cube 组一个独立任务，partial C 不覆盖；
本组 READY 后一次 AIV 屏障，再由 batch owner 求和，避免引入第二次全局同步。
K 归约采用固定树，不用原子加；浮点舍入顺序与 R14 可能不同。

## 文件与顺序

| 文件 | 用途 |
|---|---|
| R23_SPLIT_K.asc | 优先提交的性能候选 |
| R14_CONTROL.asc | 与已通过 R14 字节一致，用于相邻测量对照 |
| R23_K1_CONTROL.asc | 同一个新架构强制一段 K，分离 K 并行与新合并流程的影响 |
| G01_B1_OFF.asc | 在已知范围内 B==1 时绕过 R03 |
| G02_M64_OFF.asc | 在已知范围内 M≤64 时绕过 R03 |
| G03_N128_OFF.asc | 在已知范围内 N≤128 时绕过 R03 |
| G04_MN4096_OFF.asc | 在已知范围内 M×N≤4096 时绕过 R03 |

每个 .asc 都是独立完整提交，只选一个，不能拼接。G 系列是故意 bypass 的诊断文件，不能作为冲榜版。
R23 不依赖几何探针结果，可以先测。若要先完成用户提出的几何确认，按 G01/G02/G03/G04 独立提交即可；
Case15 从约 37 回到约 112 μs 支持对应条件。保留整张 15 点结果和文件名。

R23 先验收全部点。性能比较使用相邻 R14/R23 重复结果，不能用单次亚微秒差异认定收益。
若 R23 没有明显收益，再用 K1 判断新增合并开销，结合 G 系列确认实际几何及是否有足够空闲核。
若 R23 比 K1 快而仍慢于 R14，说明 K 并行有作用、当前合并/同步成本仍过大；
若 K1 比 R14 快，说明新消费者本身也贡献了收益。
编译失败、运行 TLE、精度失败和性能无收益应分别记录；没有日志时不推定根因。

## 已完成与待验证

三版各 116 次普通源码模型执行、58 次重复核对通过；R23 96 次走新路径、20 次回退。
K1 普通输出逐位等于 R14；Split-K 的二进制分数样本逐位等于 R14，一般随机输入独立对照 FP64。
每版 host 记录桩覆盖 8 个入口、1083600 个元数据计划、19092 个任务/分片组合；
4 个几何 guard 共 36000 次检查。错误 K 起点、错误归约、缺失屏障、错误 dtype 绑定均被拒绝。

**尚未本地 CANN 编译或 NPU 运行**。CPU 模型不是设备仿真，不能证明硬件同步、实际精度或性能；
未宣称全合法数值域通过。没有为 R23 填写平台 Pass、分数或预测耗时。
源文件 SHA256 见 MANIFEST.json，检查结果见 CPU_CHECKS.json / DISPATCH_CHECKS.json。
'''
    build.write(build.OUT/'README.md',readme)
    build.write(ROOT/audit,f'''# BatchMatmulMaxSum 当前审计：R14 基线，R23 转向长 K 并行

2026-09-27。R14 保留为已获 15/15 Pass 的基线。用户反馈 R22 无用，本轮不继续 Native small-K 调参，
而针对新证据指向的 Case15 小输出、超长 K 实现 **Cube Split-K**。
R23、单分片 K1 对照和四个几何 probe 已生成并完成本地检查；平台编译、精度与性能尚待提交。

## 本轮判断

用户的新 C512/C1024/C2048/C4096 的 Case15 耗时为 108.65/113.67/112.77/112.83 μs，
均值 111.98 μs，与 A01 R03_OFF=112.60 μs 一致。按用户给出的条件 bypass 作用域，
支持 K≥4096；结合 R03 guard 得到 4096≤K≤8192 且 32 对齐。
B 系列给出的范围为 16≤M<128、16≤N<256，均 16 对齐，B<cores。

这使“空间并行不足而 K 串行过长”成为更有针对性的优化假说。
但 **B=1、M≤64、N≤128 不能由 P02 无反应直接确证**，硬件瓶颈也尚未由 profiler 证明。
新 A/B/C/P02 探针源码/hash 未收到；结论是基于用户描述的实验作用域，不冒充独立复现实验。
[完整证据记录](V11_results/2026-09-27_case15_long_k/AUDIT.md)。

## 已实现的路线

{rules}
每个 `(batch,M tile,N tile,K shard)` 分配一个 Cube 组；K 以 32 对齐分段，
各段最少 512、最多 16 段，全部任务驻留。沿用 R03 的 K128 搬运/转换/MMAD 底层流程。
每组写独占 partial C，先通过本组 READY、再通过 AIV 屏障完成发布。
每个 batch 的 AIV owner 按固定树合并所有 K 分片，之后做 max(N)、sum(M)。
没有原子累加、没有对 K 分片提前取 max、没有 partial 槽覆盖，也不需要第二次全局屏障。

例 `B=1,M=32,N=64,K=4096,cores=20`，从单组 32 个 K128 步骤变成 8 组、每组 4 步。
输入总字节不变，有效 C 中间流量扩大 8 倍。该例不是 Case15 的已知精确形状，
工作量变化不等于 8 倍实测提速。分片上限和最小 K 段长仍需平台调优。
K1 使用同样 guard 和消费流程，仅 S=1；四个 G probe 分别确认 B==1、M≤64、N≤128、MN≤4096。
[实现、同步推导、资源上界及 API 依据](V11_split_k/DESIGN.md)。

## 验证与边界

R14/K1/R23 各 116 次普通源码模型执行、58 次重复核对，普通精度失败 0；
R23 新路 96 次、回退 20 次。覆盖 dtype、TA/TB、K 尾块、两维空间尾块、多 batch、核数不足、负值与零。
K1 普通输出逐位一致；Split-K 在二进制分数样本上逐位一致，一般随机样本独立对照 FP64 黄金值。
每次核对实际读写流量与 MMAD 数量，模型样本最大绝对误差 3.81469726562e-6。

实际 host/entry 记录桩每版检查 48 次发射/回退、全部 8 个入口、1083600 个元数据计划、
19092 个 K 分片/任务覆盖组合和 36000 次探针 guard。四项故障注入均被拒绝。
[源码检查](V11_split_k/CHECKS.json) / [分派检查](V11_split_k/DISPATCH_CHECKS.json)。

本地没有 CANN/NPU 环境。上述为 CPU 源码模型/记录桩，不能代替目标编译、设备流水与 cache 验证。
Split-K 改变 FP32 K 累加顺序，不能承诺一般输入逐位相等；全合法数值域精度未证明，
也没有将历史 FP32 消去/中间溢出限制标为修复。

## 状态与提交

优先提交 [R23_SPLIT_K.asc](BMMS_V11_R23/R23_SPLIT_K.asc)。
[提交包](BMMS_V11_R23_提交包.zip) 附 R14 控制、K1 消融、G01–G04 与[说明](BMMS_V11_R23/README.md)。
R23 覆盖已知范围，不必等待三项几何假说确证。先验收全部 15 点，再看 Case15 的稳定响应；
用相邻 R14/R23 重复提交判断收益，避免把测评波动或实时变化的标杆列当成自己的提速。

用户报告的 4.05 μs 最优列仅作线索，含义/时点未独立核验；不由此预测得分或名次。
R22 “没用”只记录定性反馈，未收到 Pass 数或逐点时间；R20 仍为无日志的编译失败，根因未确认。
旧源码和包冻结，上轮报告见[历史审计](audit_current/AUDIT_R22_DELIVERY.md)。
归档：[CANN/v11](https://github.com/Pengyiyan0411/CANN/tree/v11/BMMS)。
''')
    links=[('R23 单文件','BMMS_V11_R23/R23_SPLIT_K.asc'),('提交包','BMMS_V11_R23_提交包.zip'),
           ('提交与消融说明','BMMS_V11_R23/README.md'),('当前审计',audit),('Split-K 设计','V11_split_k/DESIGN.md'),
           ('源码检查','V11_split_k/CHECKS.json'),('分派检查','V11_split_k/DISPATCH_CHECKS.json'),
           ('Case15 新证据','V11_results/2026-09-27_case15_long_k/AUDIT.md'),('上轮快照','audit_current/AUDIT_R22_DELIVERY.md')]
    index='''# BatchMatmulMaxSum：R14 基线，R23 小输出长 K 并行

R23 依据真实 B/M/N/K、dtype/布局和核数选择 Cube Split-K；各段求和成完整 C 后才做 max(N)/sum(M)。
未命中条件仍走 R14。附单分片对照和四个几何探针。本地源码模型检查通过，CANN/NPU 验证待提交。

'''+''.join(f'- [{label}]({path})\n' for label,path in links)+'''
```powershell
python V11_split_k/build.py
python V11_split_k/run_checks.py --resume
python V11_split_k/check_dispatch.py
python V11_split_k/update_docs.py
python V11_split_k/package.py
```

R22 收到定性无收益反馈；R20 编译失败且无日志。旧源码、结果、提交包保持冻结。
审计快照生成需要 CANN_archive 中的历史 commit。
'''
    build.write(ROOT/'README.md',index);cann=index
    for _,path in links:cann=cann.replace(']('+path+')','](BMMS/'+path+')')
    build.write(HERE/'CANN_README.md',cann.replace('```powershell\n','```powershell\ncd BMMS\n'))
    status=json.loads((ROOT/'ARCHIVE_STATUS.json').read_text(encoding='utf-8'))
    status.update(latest_feedback='R22 not useful. User supplies Case15 K>=4096 scoped bypass evidence and requests a new approach.',
        R22_platform_result_received=False,R22_qualitative_feedback='no useful improvement',R22_full_result_table_received=False,
        case15_long_k_evidence=evidence,R23_source_sha256=build.sha(build.OUT/'R23_SPLIT_K.asc'),
        R23_cpu_source_runs_per_version=116,R23_cpu_repeat_checks_per_version=58,
        R23_cann_compiled_locally=False,R23_npu_tested_locally=False,R23_platform_result_received=False,
        next_action='Submit R23_SPLIT_K.asc and verify all 15 cases; use adjacent R14 controls, optional K1 ablation and G01-G04 geometry probes.')
    build.write(ROOT/'ARCHIVE_STATUS.json',json.dumps(status,ensure_ascii=False,indent=2)+'\n')
    print('Case15 evidence, R23 usage and audit written; R22 audit preserved.')
if __name__=='__main__':main()

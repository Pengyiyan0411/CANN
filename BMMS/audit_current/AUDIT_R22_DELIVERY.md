# BatchMatmulMaxSum 当前审计：R20 编译失败，R14 基线重做 R22

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

| 输入条件（原 Native 域内） | R22 内核 |
|---|---|
| N=16/32、M>32；K=32/64/128 | 64×32 窄列 |
| M=16/32、N≥256 且为 256 倍数；K=32/64 | 32×256 宽列 |
| M/N 均≥128 且均为 128 倍数；K=32/64/128 | 128×128 稠密 |
| 未命中，或新计划减少可用核组 | 原 R14 |

ShortN 缩小存储和向量处理宽度；ShortM 合并 N tile；Dense 增加 M 高度以复用 B。
三条路径都同步修改生产者、消费者和 workspace；保留全 K 的 FP32 累加、行 max 和 M 求和。
R14 原源码除了新增片段、一个 host 调用和首行版本注释，可逐字还原。
[完整条件、容量、代价和 API 依据](V11_shape_dispatch/DESIGN.md)。

| 合成控制例（B1、1 核组） | 指标 | R14 → R22 |
|---|---|---|
| M256/N16/K128 | 填充元素数 | 66048 → 16896 |
| M32/N512/K64 | MMAD / Fixpipe 调用数 | 4 → 2 |
| M256/N512/K64 | MMAD / Fixpipe 调用数 | 16 → 8 |

逻辑工作量减少不等于设备提速。ShortM 的向量填充可能增加，Dense 的 L0C 和 ring 更大，
最终盈亏待平台。也不能保证未知形状的 Case 5 会进入新分支。

## 已完成验证

每版 788 次普通源码模型运行、402 次重复核对，与 R14 普通输出逐位一致。
R22 的 ShortN/ShortM/Dense 实际源码分别执行 120/92/113 次，
Native 回退执行 172 次。每版 497 次 Native 独立流量公式核对。
覆盖 FP16/BF16、四种布局、K32/64/128、尾块/尾 packet、多 batch/pM/pN、负值和零。

真实 host/入口记录桩：150 次检查覆盖全部 64 个新入口和
86 次不分配/不发射回退；2016 个元数据计划中验证了
123 次核组减少回退。错误归约步长、遗漏宽列上半区和错误 dtype
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

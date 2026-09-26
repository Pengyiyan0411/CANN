# BatchMatmulMaxSum 当前审计：R14 基线，Native Case 5 专项 R20/R21

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

| 控制例 B1/M256/N1024/K128/1核组 | R14 | R20 | R21 |
|---|---:|---:|---:|
| MMAD 调用 | 32 | 16 | 32 |
| A→L0A 字节 | 524288 | 262144 | 65536 |
| LoadData 调用 | 384 | 192 | 264 |
| B→L0B 字节 | 1048576 | 1048576 | 1048576 |
| Fixpipe 调用 | 32 | 32 | 32 |

R21 在短 N 控制例中 B LoadData 32→4。这些不是隐藏测试点，也不能换算为设备提速。
原 GM A/B 读取、C 元素覆盖、Fixpipe 输出及 READY/FREE 协议已核对保持一致。

每版 624 次普通运行、312 次重复核对，原有结果及新用例与 R14 逐位一致。
覆盖 3 种 K、2 种 dtype、4 种布局、尾 N、跨 AM/batch、负数/零和线程顺序变化；
每版 333 次 Native 逻辑流量核对。
R20 宽 N 和 R21 A0 复用各执行 245 次。
错误 Fixpipe 源偏移和错误 A0 行偏移均被负向测试拒绝。
真实 NativeEntry 记录桩检查 99840 项，选择器 2080 项，
原计划检查 6912 项。

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

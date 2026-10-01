# R45：只减少 R43 的整块预清零

2026-09-28 更新：用户回报 Case8 为 **62.54、62.47 μs**，与 R43 的 62.45 μs 无可见差异，R45 不晋升。详见 [最新反馈](../V11_results/2026-09-28_r45_case8_feedback/FEEDBACK.json)。下文是首次交付时的实现与验证记录；原提交源码、CPU 检查结果和 ZIP 快照保留。

历史提交文件为 **[R45_CASE8_PACK_TAIL_ZERO.asc](R45_CASE8_PACK_TAIL_ZERO.asc)**，完整源码。目录中已有另一份 `R44_CASE8_DIRECT_RAGGED_MACRO.asc`，因此当时采用 R45 编号；没有合入或修改那份 R44。

## 改了什么

原 R43 每个输入搬运块先整块清零，再用真实数据覆盖大部分区域。R45 让 DataCopyPad 覆盖真实数据及其显式行尾 padding，Vector 只写两种剩余区域：

1. K 向 32 元素补齐、DMA 行向 16 元素补齐之间的额外 16-word 空隙；用一条带 repeat stride 的 Duplicate 覆盖多行。
2. 补出的整行；用连续 Duplicate 清零，并把真实行数下限约束为 0，覆盖完全不含真实行的 job。

除了文件头说明，源码改动仅位于 `PackInputs`。原 guard、planner、原 Macro 生产端、归约消费端、workspace、双槽和分派顺序均按原字节保留。所有原有 event、fence、跨核通知调用和顺序保留。即使某个 job 无需清零，仍保留 `MTE3 → V → MTE2` 的槽复用依赖。

## 本地验证

| 检查 | 结果 |
|---|---|
| 实际源码函数提取后进行 CPU 执行 | R43 64 次、R45 64 次；每个版本 8 组尺寸 × 四布局 × 两种调度 |
| 参考结果 | 独立二维矩阵补零参考；原始 16-bit 数据逐位一致，新增区域均为 +0 |
| 数据覆盖 | 每个输入覆盖全部 65,536 种原始 16-bit 模式；UB 初始为脏数据 |
| 全范围补齐几何 | 63,488 个单侧描述、3,577,521 个 job；包括 26,055 个纯补齐 job |
| gap Duplicate 参数 | 实际最大 repeat=31，repeat stride=80 个 32 B 块，均未截断 |
| 故障敏感性 | 故意省略行间空隙、整行补零两种故障，均被参考检查检出 |
| 非目标代码 | 去掉版本说明后，`PackInputs` 之外与 R43 按字节一致 |
| 完整 CANN 编译 / NPU 实测 | **未执行**；本地无相应编译器和设备 |

CPU 模型中的两个版本读取和写出 GM 的字数相同；测试集合内 Vector 清零从 209,108,992 个半精度元素降到 1,834,496 个。这是合成输入的工作量检查，**不能换算为 Case8 的性能收益**。FP16/BF16 算术、完整算子的设备精度及跨核屏障实际调度未在本地验证。

## 依次测评

| 版本 | Case8 | 其他点 | 状态 |
|---|---:|---|---|
| 冻结 R25 | 约 91 μs | 历史对照 | 保留回退 |
| 原 R43 | 用户报告 62.45 μs | 用户报告变化在波动范围内 | 本轮比较基线 |
| R45 | 待测 | 待测 | 不提前晋升 |

按 **R43 → R45 → R45 → R43** 交替测评，记录完整 15 点。先确认精度全部通过，再看 Case8 改善是否可重复、其他点是否出现可重复退化。`CONTROL_R43.asc` 与原 R43 完全相同。

这次只尝试第一项。R45 反馈后，第二项测试完整 C 块的读取；第三项测试可直接复用原输入的一侧。后两项仍应分别从原 R43 派生，等独立收益确认后再合并。

## 文件与复现

- [候选与 R43 的差异](R45_vs_R43.diff)
- [检查结果](CPU_CHECKS.json)
- [版本身份和状态](MANIFEST.json)
- 生成与检查脚本：`../V11_impl_r45/build.py`、`../V11_impl_r45/check.py`。
- 在 BMMS 目录执行 `python V11_impl_r45/check.py` 可复现 CPU 检查；这不是设备编译命令。

`Duplicate` 使用官方已提供的连续 mask、repeat 和 stride 重载；参数的块单位及 32 B 地址对齐要求已核对：[CANN 9.0 Duplicate](https://www.hiascend.com/document/detail/en/CANNCommunityEdition/900/API/ascendcopapi/atlasascendc_api_07_0088.html)。DMA 仍沿用 R43 的显式右侧 padding 和 stride：[CANN 9.0 DataCopyPad](https://www.hiascend.com/document/detail/en/CANNCommunityEdition/900/API/ascendcopapi/atlasascendc_api_07_0265.html)。

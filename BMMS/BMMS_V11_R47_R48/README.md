# R47 / R48：分别尝试 Case13 和 Case7

**最新实测**：R48 点 7 为 9.44 / 9.70 μs，保留为有收益候选；R47 点 13 为 19.23 μs，不采用。三次均 15/15 Pass。R43 仍为冻结对照。详见 [完整反馈](../V11_results/2026-09-28_r47_r48_feedback/RESULTS.md)。以下为交付时的设计和检查记录。

2026-09-28。两份都是可以独立提交的完整 `.asc`，各自从原版 R43 派生，**没有相互合并，也没有晋升为新 baseline**。所有交付件及检查脚本都位于工作目录 `C:\Users\cc\Downloads\BMMS` 下。

| 文件 | 目标 | 相对 R43 的唯一新增路线 |
|---|---|---|
| [R47_NATIVE_NARROW_DIRECT.asc](R47_NATIVE_NARROW_DIRECT.asc) | 优先试 Case13 | B=1、K=128、M>256、N=48/64 的窄 N Native 专用执行计划和消费者 |
| [R48_RESIDUAL_BATCH_OWNER.asc](R48_RESIDUAL_BATCH_OWNER.asc) | 随后试 Case7 | 小 M/N、K<512、多 batch 的 R03 residual 改为每个核组负责完整 batch |
| [R43_CASE8_PADDED_MACRO.asc](R43_CASE8_PADDED_MACRO.asc) | 冻结对照 | 与历史 R43 完全相同 |

## R47：改变 M 分配和窄 N 消费过程

旧 N01–N05 的强证据是 Case13 的 B=1、K=128、M/N 都大于 32 且 16 对齐。新 report 提出的 M>256、N≤64 与旧证据相交后，只剩 N=48 或 64；这条窄 N 结论仍是 report 级证据，不把未归档的原始探针当成已核验事实。

R47 在 Native 分支内部、R25 的 `TryLaunch` 前插入调用。附加 guard：`B==1 && K==128 && M>256 && M<=8192 && M%16==0 && (N==48 || N==64) && 2<=cores<=64`。原来的输入检查和 Native family 排除规则仍在前面执行。

具体变化：

1. M 按 16 行对齐均分到最多 `min(cores,M/16)` 个核组；区间内的 Cube tile 仍最多为 64 行。调度单位与计算 tile 分离，避免简单固定 M32 把 MMAD 数量不必要地翻倍。
2. N 是一个完整的 48/64 列面板，`pN=1`，L1 的 BN 从 512 收到 64，ring 的 TN 从 128 收到 64。
3. 每个 tile 独立发布。两侧 AIV 各读一半有效行，直接以实际 N 做 `WholeReduceMax`。不做通用 N 面板最大值累积、不填充无效列，也不执行 128 列折叠。
4. 保留完整 M 个行最大值和一次 `SyncAll`，最后仍由一个 AIV 对完整 M 执行一次 `ReduceSum`。没有改成分组求和或 atomic，避免引入额外求和顺序变化。

代价：更细的 M 分派会重复读取 B，并增加某些 shape 的 MMAD、Fixpipe 和通知次数。是否抵消减少空闲核、消费者通用逻辑和 ring 空间带来的好处，需要真实测评。这不是 R30 的全域 M128 替换，也不是 R26 的通用 packet DMA 调整。

## R48：完整 batch 归属，去掉跨组归约

Case7 的强证据：R03 residual，M<128、N<256、256≤K<512，M/N 16 对齐、K 32 对齐，B<cores。`B>1` 来自新 report，旧 one-group stress 本身不能证明它。R48 明确限制 B>1；若实际 B=1，则继续走原 R43 路线。

附加 guard：`B>1 && B<cores && M<128 && N<256 && K<512 && bmms11d::ResidualEligible(...)`，并保留原 family 排除。调用放在原 R03 前，R06 和 Split-K 的优先级不变。

R48 完整复用 R43 的 `bmms11d::StagedProducer`，K128 分段累加、输入布局和 MMAD 顺序不改。计划设为 `pM=pN=1, tasks=blocks=B`。每个核组算完一个 batch；其中一个 AIV 读取全部有效行、完成 Max(N) 和完整 M 的 ReduceSum，另一个 AIV 仍参与 READY/FREE 握手。

移除行最大值的 GM partial、回读和 `SyncAll`。N 尾部仍填负无穷，保证全负结果不会被零 padding 污染。这与无收益的 R29“整 K 驻留 L1”是不同实验。

代价：最多只启用 B 个核组，会失去原先 M/N 的空间并行。旧 Case7 单组压力实验只能证明并行度重要，不能证明 batch 独占一定获益。因此 R48 是一次有明确取舍的独立候选，不提前承诺加速。

## 已执行的本地检查

- [MANIFEST.json](MANIFEST.json)：从每个候选移除新增模块和单行分派后，原始 R43 可按字节恢复。冻结 R43 SHA256 为 `15e2c9a0f73e7534c26400107389dcd8e5cf685b5f6f477c7a3684ad3991df2d`。
- [CPU_CHECKS.json](CPU_CHECKS.json)：实际 producer/consumer C++ 的 CPU 存储布局、数值和事件模型回放；基线 132 次、候选 132 次，包括重复执行、FP16/BF16、NN/NT/TN/TT、尾块、全负值、零值、K 尾段和最大 M。比较完整 M 的归约结果，并检查 ring 读写守恒、事件耗尽、输入未修改、GM/UB 边界和 partial 覆盖。
- [HOST_CHECKS.json](HOST_CHECKS.json)：69,524 次完整入口分派核对；60,810 次非目标调用的 launch/plan/workspace 记录与 R43 一致。包含 R25 小输出元数据域 256 次、Split-K 620 次、R43 padded Case8 128 次保护检查。
- [FAULT_CHECKS.json](FAULT_CHECKS.json)：刻意让 R47 消费未初始化的 N padding、让 R48 用零填充 N 尾部，检查能否拒绝这些错误。

CPU 检查不是 CANN/Bisheng 编译、真实 Cube 舍入验证或 NPU 时序模拟。本机未执行板上编译及性能测试。新增代码可能影响编译结果与实际时延；源码分派保护不能替代全 15 点回归。

复现脚本在 `../V11_impl_r47_r48`：依次执行 `python check.py`、`python check_host.py`、`python check_faults.py`。请从该目录执行，或从工作目录用对应相对路径执行。

## 测评顺序和保留条件

1. 先提交 R47，对比 Case13，同时看 Case14、Case5 和其他点。不要用右侧“最优用时”列作为本次运行结果。
2. 再独立提交 R48，对比 Case7。R48 不包含 R47 的改动；仍与 R43 对照。
3. 每个候选与 R43 交错跑至少三轮，比较每点中位数及波动。目标点有稳定改善、15 点全部 Pass、其他点没有重复出现的退化，才考虑合并。

若目标点始终无变化，窄条件未命中和优化无收益都仍可能；不要仅凭时延不变反推 shape。R43 保留到验证结束。

# R22_SHAPE_SWITCH：按输入元数据选择固定内核

2026-09-27。独立基于用户指定的 R14；R20 平台编译失败且没有日志，确切错误未确认。
本版把策略选择集中在 host，分别实例化 ShortN、ShortM、Dense 的生产者和消费者。
各内核具有固定的片上布局、GM packet 布局和向量步长。

## 分派规则

共同前提是 R14 原有 Native 路由：M/N≥16 且 16 对齐、K∈{32,64,128}，
FP16/BF16，并排除 Tiny/Resident。B、M、N 和实际核数继续接受原入口校验；
新选择器另限制 B/核数为 1–64、M/N≤8192。

| 策略 | 明确命中条件 | TM×TN | AM / BN |
|---|---|---:|---:|
| ShortN | N=16 或 32，M>32，K=32/64/128 | 64×32 | 256 / 32 |
| ShortM | M=16 或 32，N≥256 且 N%256=0，K=32/64 | 32×256 | 32 / 512 |
| Dense | M、N 均≥128，且均为 128 的倍数，K=32/64/128 | 128×128 | 256 / 512 |
| R14 | 其余形状，或候选的 blocks 小于原 R14 blocks | 原 64×128 | 原 256 / 512 |

每次调用读取真实 B/M/N/K、dtype、TA/TB 和 cores：先按表选择几何形状，再选择 K、
dtype、转置的独立入口。共有 24 个 ShortN、16 个 ShortM、24 个 Dense 绑定。
不读取输入数值、不使用测试编号、不跨调用缓存选择结果。

例如 B1/M32/N512/K64/1 核组选择 ShortM；同布局的 B1/M16/N256/K64/20 核组，
加宽 N 会把原本可用的两个任务压成一个，因此回退 R14。B1/M256/N128/K128/1 核组
选择 Dense；B1/M128/N128/K128/20 核组同样因并行度损失回退。
这些是可复现的合成例子，不是对 Case 5 隐藏形状的推断。

`MakePlan<TM,TN,AM>` 按新 tile 网格重算 pM/pN，并沿用 R14 的工作量、GM 读取、
partial 和分片开销模型。只在候选中比较该成本，不把不同 tile 大小的无量纲成本直接对比。
blocks 保护只防止减少可用核组，不能保证硬件性能提升；真实盈亏仍要提交对照。

## 三种策略的具体工作

ShortN：缩小消费者每行的存储和处理宽度，N16 用负无穷填充到 N32。
GM ring 每核组从 256 KiB 缩为 64 KiB，归约只处理 32 列，省掉原来的 128→64 折叠。
矩阵乘仍用实际 mr/nr，所以不声称这一路减少 MMAD 运算量。

ShortM：M 的分配高度匹配 16/32 行输入，把两块 N128 直接变成一块 N256。
生产者一次 MMAD、一次 Fixpipe 写一个新 tile；消费者按 N256 处理，先分别合并
第 0/128、64/192 列起点的两个 64-lane 区间，再合并到前 64 列进行归约。
只支持 K32/64，因为双槽 N256/K128 的 L0B 要 128 KiB，超过本路线采用的 64 KiB 上限。
向量填充元素可能增加，这是换取较少 Cube/Fixpipe 指令的代价。

Dense：M64 改为 M128；N 仍为 128。对整 tile 矩阵，MMAD/Fixpipe 数量减半，
每个更高 M tile 复用一次 B→L0B 搬运。消费者的每个 AIV 最多处理 64 行。
L0C 使用 128 KiB，GM ring 每核组为 512 KiB；占用变大也是潜在性能代价。

所有策略保留完整 K 的 FP32 累加和每行 max 后对 M 求和。packet 仍为四个 tile、
双槽 READY/FREE 协议；生产者和消费者使用同一组 TM/TN/AM/BN。
尾 packet、M 尾块、多 batch 的序列计数，及跨 pN 的最终 max 合并保留 R14 的控制方式。

## 容量与地址

以下是源码申请的最大容量，不是目标编译器的分配报告；KiB=1024 字节。

| 每核申请上限 | ShortN K128 | ShortM K64 | Dense K128 |
|---|---:|---:|---:|
| L1 A+B | 80 KiB | 132 KiB | 320 KiB |
| L0A 双槽 | 32 KiB | 8 KiB | 64 KiB |
| L0B 双槽 | 16 KiB | 64 KiB | 64 KiB |
| L0C 双槽 | 16 KiB | 64 KiB | 128 KiB |
| GM ring / 核组 | 64 KiB | 256 KiB | 512 KiB |

GM partial 仍为 `B*pN*M*sizeof(float)`。消费者 UB 申请总和：
`4*TM*TN + 2*TM + 4*AM + 12*M + 32` 字节。
在各自命中域内，ShortN 最大 107680 B、ShortM 最大 33376 B、Dense 最大 165152 B，
均小于本路线采用的 192 KiB UB 上限；编译器附加开销仍需平台检验。

LoadData 保留 R14 的 ZZ/ZN 排布和 512 B 分形起点；Fixpipe 的 srcStride 为实际 mr，
dstStride 为对应 TN。向量 repeat 的源步长按 `TN/8` 个 32 B block 计算，
TN32/128/256 对应 4/16/32。WholeReduceMax 的 mask 为 32 或 64，repeat≤64，
dstRepStride=1，使用独立 rows 缓冲。

接口核对依据：[WholeReduceMax（A2 支持 float 与 ORDER_ONLY_VALUE，mask/stride 定义）](https://www.hiascend.com/doc_center/source/en/CANNCommunityEdition/850/API/ascendcopapi/atlasascendc_api_07_0079.html)、
[Load2D](https://www.hiascend.com/document/detail/en/CANNCommunityEdition/900/API/ascendcopapi/atlasascendc_api_07_00169.html)、
[Mmad](https://asc.gitcode.com/api/SIMD-API/basic_api/cube_compute_ISASI/mmad_compute/Mmad.html)、
[Fixpipe](https://www.hiascend.com/doc_center/source/en/CANNCommunityEdition/900/API/ascendcopapi/atlasascendc_api_07_0251.html)。

## 编译失败处理与验证边界

R20 中 `UseWideN` 没有 `__aicore__` 标注，却由设备 `NativeEntry` 调用，这是可定位的
源码风险。但没有编译日志，不能认定它就是用户看到的首个编译错误。
R22 从冻结的 R14 生成，不继承 R20/R21 生产者；新 host selector 不会由设备函数调用，
每个新入口只实例化一组固定资源布局。原 R14 fallback 的其余源码可逐字还原。

`run_checks.py` 提取提交文件中的真实生产者/消费者，验证显式内存、分形布局、
事件配对、ring 覆盖、逻辑流量和输出；与 R14 在相同输入上对比。
`check_dispatch.py` 编译真实 host Select/TryLaunch 和 64 个真实入口的记录桩版本，
检查 dtype、布局、K、几何尺寸、分配、launch blocks 和回退。
只有 launch 语法与底层设备/ACL API 被 CPU 记录桩替代。

错误的窄列归约步长、遗漏 N256 上半列归约、错误 dtype 入口三项故障注入均被拒绝。
次数和 SHA256 见 CHECKS.json / DISPATCH_CHECKS.json。
没有本地 CANN 编译、NPU 执行或真实性能计时；原有三项极端数值限制仍存在。
Case 5 已定位 Native，但精确形状未知，不能保证本版新分支一定命中它。

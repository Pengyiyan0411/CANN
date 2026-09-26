# R20 / R21：基于 R14 的 Native small-K 专项优化

2026-09-27。父版固定为 R14_FLEX_SINGLE_WAVE，SHA256：
`64eb6eeeb10d2418845d2026b9e9fdd2088d0a3ad1decb0a1bfc46d65cfa78fe`。
两版独立派生，不包含 R15–R19 的 K 覆盖或大 K 驻留修改，也不叠加彼此。

## 诊断依据与实现范围

用户给出同一组诊断实验的 Case 5：P01/R06 stress 7.71 μs，P02/R03 stress 7.58 μs，
P03/Native stress 14.11 μs，P04/Tree stress 7.20 μs。P03 与其余三项的中位数 7.58 μs
相比为 1.86 倍。结合用户说明的改动作用域，将 Native small-K 作为本轮已定位的工作路径。
不再用单点绝对耗时猜测路由；其他 probe 的阴性反应不作为独立的排除证明。

R14 真实入口要求 M、N 均至少 16 且 16 对齐，K 为 32/64/128，并排除 Tiny、Resident。
在该域中，只能属于 ShortM_SmallK、ShortN_SmallK 或 Dense_SmallK。具体 B/M/N/K、
dtype、TA/TB 仍未知，优化依据实际公开元数据，源码不引用测试点编号或输入内容。

用户本轮的 P03/Native stress 是新诊断的标签。仓库旧 ProbePack 中的
P03_TREE_OFF 不同，不能拿那个文件作为新 P03 的源代码或 hash。新 probe 的完整源码、
全部测试点及重复样本未收到，按“用户提供的作用域与计时”记录证据。

R05 曾实现跨 N 面板延迟 Max 归约和完整 C 块免填充，没有确认稳定收益；本轮不重复该方向。
R14 Native 的 A 已在 L1 按 AM=256 驻留，但每个 N 微块仍重新搬到 L0A。
原 MMAD 为 64×128×TK；每个结果微块一次 M_FIX 等待、一次 Fixpipe，四块组成 GM packet。

## R20_NATIVE_WIDE_N

保持原分核、AM=256、BN=512、全部 AIV 代码、64×128 GM 微块和四微块 packet。
新增 WideNProducer，在每个任务 N 分片至少有两个微块时使用：`nTiles >= 2*pN`。
该条件等价于所有 `floor((ns+1)*nTiles/pN)-floor(ns*nTiles/pN) >= 2`。
一/二块混合的分片保持原生产者；不为了进入新路径强行减少并行度。

生产者一次计算至多 64×256×TK，保留完整 K 的 FP32 点积，再以两个 Fixpipe 按原次序
写回两个 64×128 微块。尾 N 可以只有一个微块或不足 128 列，均使用实际 nr。
L0C 中第 ni 列起点为 `(ni/16)*mr*16`，源 NZ 的 srcStride 仍为 mr。
微块 seq 与 MMAD emitSeq 独立：前者控制原 packet，后者控制两个加宽的 L0C 槽。

K128 时两个 256 列的 L0B 槽会超过 64 KiB，因此只保留一个完整 L0B 槽。
每次复用前等待上一 MMAD 的 M_MTE1；C 两槽分别等待 FIX_M。
沿用原 M_FIX 完成等待后才启动 Fixpipe；保留所有四块 READY、跨槽 FREE 和最后残包发布。
单次合并可能横跨 packet 边界，逐个输出微块检查槽位归属，不假设 packet 总从偶数 tile 开始。

| K128、每 AIC 申请 | R14 | R20 命中 |
|---|---:|---:|
| L1 A+B | 320 KiB | 320 KiB |
| L0A | 32 KiB | 32 KiB |
| L0B | 64 KiB | 64 KiB |
| L0C | 64 KiB | 128 KiB |

收益来源是合并 MMAD/M_FIX 指令以及减少重复 A→L0A 搬运，不减少矩阵乘 FLOP、B 搬运或
C 的 FP32 GM 流量。代价是 L0C 占用翻倍，L0B 单槽限制预取；真实性能只能由平台比较决定。
这属于 Native 的全 K 宽 N MMAD，不是旧 R06 大 K 宏块路径的再次提交。

## R21_NATIVE_L0_REUSE

不改变 MMAD 形状、K 顺序、L0C、Fixpipe 或消费者，优化 L1→L0 搬运。

1. 当所有 N 分片至少有两个微块时，把当前 AM 段的完整 A 一次排入 L0A；每个 MMAD
   用 `mo*TK` 选择该段中的行。跨 N 面板复用，跨 M 段或 batch 重新加载。
2. 复用域以外维持 A2 两槽。A 的 LoadData 在 M/16 与 K/16 中选择较短的指令循环轴，
   用 repeatTimes 与 dstGap 表达另一个方向，不改变 ZZ 排布。
3. B 在 N/16 与 K/16 中选择较短循环轴；N<K 时减少指令，保留 ZN 排布和 B2 两槽。
   例如 K128、N16，从每块 8 次 B LoadData 变为 1 次，搬运字节不变。

resident A2 在 TK128 时为 `256*128*2 = 65536` 字节，达到 64 KiB 上限；
TK32/64 分别为 16/32 KiB。未进入复用域时仍使用旧的 `2*64*TK*2` 字节。
每个 M 段末尾消费未归还的 M_MTE1 事件，之后才允许覆盖整份 A2。
abPending 按两个 L0B 槽记录事件，避免 M 段结尾等待后在下一段重复等待而挂起。
没有新增 event ID，M_FIX 和 FIX_M 次序沿用 R14。

所有 LoadData 起点维持 512B 对齐。切换循环轴后的目标间隔以 512B 分形为单位，
最大 repeat 16，dstGap 最大 7。TA/TB 的源 NZ 步长按实际 ar/br 和 TK 计算。

## 离线验证与平台判定

`build.py` 能把允许的局部修改还原为 R14，并逐字检查剩余源码一致。
`check_dispatch.py` 编译真实 NativeEntry（生产者以记录桩代替），验证元数据选择；
`run_checks.py` 从完整候选提取真实生产者，运行已有的显式内存、分形、事件和 ring 所有权模型。
检查所有三种 K、两种输入 dtype、四种转置，ShortM/ShortN/Dense、跨 batch、跨 AM、
N 多面板、1/2/3 个尾 packet 微块、负值/零输入及不同线程启动顺序。
逻辑流量使用独立公式核对，不把指令数减少直接换算为设备加速比例。
故意破坏 R20 的 Fixpipe 源偏移和 R21 的 resident A0 偏移，验证检查器确实拒绝错误。

确切次数、源码 hash、容量峰值和结果在 CHECKS.json；本地没有 CANN 编译或 NPU 运行。
CPU 的同步 API 模型不是异步硬件模拟器，也不能证明目标编译器的资源分配和 Cube 舍入行为。
既有三项极端数值限制保持单独记录，不宣称全输入数值域通过。

建议先提交覆盖更广的 R21，再独立提交 R20，均以原 R14 为对照。两者还不能相互合并。
观察全部 15 点 Pass 与其他 Native 点的退化；Case 5 是重点，不把它当作唯一验收项。
微小变化用相邻 R14 控制和重复提交排除波动，比较同一轮的标杆 T，不拼接各版最短时间。
R20 无变化可能是其每分片至少两块条件未命中，也可能是成本被其他阶段掩盖，不能据此推翻 Native 定位。

## 官方接口依据

本轮核对 A2 适用范围、b16 转置、LoadData 的 repeat/stride/dstGap、MMAD 布局与 Fixpipe 源步长：

- [Load2D](https://www.hiascend.com/document/detail/en/CANNCommunityEdition/900/API/ascendcopapi/atlasascendc_api_07_00169.html)
- [Mmad](https://asc.gitcode.com/api/SIMD-API/basic_api/cube_compute_ISASI/mmad_compute/Mmad.html)
- [Fixpipe](https://www.hiascend.com/doc_center/source/en/CANNCommunityEdition/900/API/ascendcopapi/atlasascendc_api_07_0251.html)

使用 A2 已有 LoadData2DParams，没有引入 Load2D V2 或更高代硬件专属指令。

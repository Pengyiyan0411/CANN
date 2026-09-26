# BMMS V9：CATLASS 路线可行性与集成边界

日期：2026-09-26。状态：**离线源码研究；未编译、未运行 NPU、没有新性能结论。**

## 1. 结论

CATLASS 值得作为“覆盖大 K 的底层 Dense Cube 主干”的实现参考和对照候选；它不是替换一个 include 就能使当前程序冲榜的成品。最合适的第一步是固定成熟 Atlas A2 模板，保留官方 `run_kernel` ABI 与单次 launch，在自定义 kernel 中组合 **全 K FP32 累加的 BlockMmad + 每核 GM 两槽 + AIV 持续 rowmax + 确定性最终归约**。

当前 P01 已有 small-K Native 和 Cube/Vector 融合流水，V9 的新增价值应明确为：把底层 Cube 路线延伸到 K>128，替换这些输入依赖的旧高层 Matmul 同步消费路径；同时用真实资源与任务所有权约束调度。没有证据支持“仅使用 CATLASS 必然更快”。

**集成方式的优先顺序：**

1. 从固定源码提取最小 A2 BlockMmad/搬运逻辑或将必要声明内联到允许提交的 `kernel.asc`；保持现有 Host 和入口约定。
2. 只有确认 Judge 编译系统提供 CATLASS include 路径后，才选择直接依赖头文件。当前没有这个证据。
3. 作为可独立对照的备选，使用同一资源/工作划分设计实现纯 Ascend C 底层主干；避免把“必须迁移整个 CATLASS 框架”设为前提。

## 2. 已装载的技能与本次适配

已完整阅读以下文件：

- `C:/Users/cc/.agents/skills/catlass-operator-design/SKILL.md`
- 该技能的 `references/design-document.md`、`matmul-templates.md`、`epilogue-components.md`、`custom-epilogue.md`
- `C:/Users/cc/.agents/skills/catlass-operator-performance-optim/SKILL.md`

用户明确只要求无算力离线分析，因此本次执行需求、源码选型和设计阶段，环境初始化、编译和 PRE/POST 性能报告均不执行。内部候选名可用 `bmms9_catlass_dense`，对外算子名和 ABI 继续遵守题目。技能中 msopgen/aclnn 工程路径与强制命名不应覆盖比赛的单文件提交接口。

技能引用的 `docs/1_Practice/10_matmul_optimization.md` 在固定 tag 不存在；实际已读同版官方优化文档 `docs/contents/advanced/catlass_optimize_guidance.md`（全文 162 行）。这是版本路径适配，不是跳过官方指引。

## 3. 固定源码与官方依据

官方源码取得自 [cann/catlass](https://gitcode.com/cann/catlass)，保存在 `V9_design/references/catlass`：

| 项 | 固定值 |
|---|---|
| tag | `v1.4.0` |
| commit | `bcb3e52b6be3004b28996fb48af65ce48710c8f4` |
| 选择原因 | 研究成熟 A2 C++ 路线，避免无意加入后续 950/DSL 依赖；不宣称它是当日最新版本 |
| 平台信息 | README 的 A2/A3 Linux 支持表及 CANN 最低版本信息；本地实际 CANN 9.0 编译兼容性尚未测试 |
| 架构 | `include/catlass/arch/arch.hpp:18` 的 `Arch::AtlasA2` |

以下文件与行号均相对该固定仓库，在线可从 [v1.4.0 源码树](https://gitcode.com/cann/catlass/tree/v1.4.0) 查阅：

| 已确认事实 | 文件与行号 |
|---|---|
| A2 资源常量 UB 192 KiB、L1 512 KiB、L0A/B 各 64 KiB、L0C 128 KiB | `include/catlass/arch/arch.hpp:18` |
| `MmadAtlasA2Pingpong<ENABLE_UNIT_FLAG>` 策略、STAGES=2 | `include/catlass/gemm/dispatch_policy.hpp:31` |
| FP16/BF16 输入均选择 float accumulator | `include/catlass/gemm/helper.hpp:95`、`:110` |
| FP32 C 写 GM 为 `NoQuant`，不必转回半精度 | `include/catlass/gemm/tile/copy_l0c_to_gm.hpp:39` |
| Pingpong 模板要求 L1.M/N 等于 L0.M/N | `include/catlass/gemm/block/block_mmad_pingpong.hpp:101` |
| Pingpong 只持有一个 L0C，而非双 L0C | 同文件 `:135`、`:337` |
| 全 K 循环、仅首个 K 分片清空 C | 同文件 `:189`、`:292` |
| 完成全 K 后才写 C 至 GM | 同文件 `:318` |
| 官方 MatmulEpilogue 默认完整 M×N workspace | `include/catlass/gemm/kernel/matmul_epilogue.hpp:90` |
| AIC/AIV 模板特化及同调度器匹配任务 | 同文件 `:119`、`:163` |
| 官方 ReverseFlag 限制单向 flag 连续计数，不是环形槽所有权协议 | `include/catlass/arch/cross_core_sync.hpp:19`、`:98` |
| mixed Cube/Vector 示例编译、include 路径由工程显式传入 | `examples/CMakeLists.txt:16`、`:60`、`:80` |
| Resource 包含 TPipe 并显式 Destroy，需防止和原程序重复管理资源 | `include/catlass/arch/resource.hpp:20` |

最新官方 [XFAI 设计文档](https://catlass.readthedocs.io/zh-cn/latest/2_Design/04_contrib/00_XAttention/03_xfai_kernel/) 另给出了 Atlas A2 “Cube 写 FP32 S 至 GM、Vector 消费”的流水范例。它只能证明类似体系可实现，不能冒充固定 v1.4.0 内存在同名 XFAI 文件，也不能作为 BMMS 已测收益。

## 4. 可直接研究的组件与必须自定义的部分

| 层 | 第一版选型 | 判断 |
|---|---|---|
| ArchTag | `Catlass::Arch::AtlasA2` | 源码确认，不能选 950 路径 |
| BlockMmad | `Gemm::Block::BlockMmad<MmadAtlasA2Pingpong<false>, ...>` | 全 K FP32 累加、可审计的初始对照；unit flag 后置作为单独实验 |
| AType/BType | `Gemm::GemmType<half 或 bfloat16_t, RowMajor/ColumnMajor>` | 两种输入类型各四布局；逻辑转置从参数判定 |
| CType | `Gemm::GemmType<float, layout::RowMajor>` | GM 中间结果不得转 FP16/BF16 |
| TileCopy | 对应 A2 `CopyGmToL1`、`CopyL1ToL0A/B`、`CopyL0CToGm` | 直接核对实际实例化与对齐需求 |
| BlockScheduler | 自定义 batch + M-owner + N-shard 调度 | 普通 GEMM swizzle 独立派发 C 矩形块，不天然保有 rowmax 生命周期 |
| BlockEpilogue | 自定义 `BlockBmmsRowMax`，内部 `TileBmmsRowMaxFp32` | 不是已有逐元素 NoSource epilogue 的简单替换 |
| Kernel | 自定义 `BmmsCatlassDenseKernel` | 官方 MatmulEpilogue 输出 D 矩阵且完整 workspace；与 y[B] 不同 |
| Host | 现有 run_kernel 内计算 tiling 和 workspace | 不移植示例 aclInit、aclrtMalloc、独立 DeviceGemm 生命周期 |

参考 `examples/00_basic_matmul` 确认 BlockMmad 组装，参考 `03_matmul_add` 的 AIC/AIV 混合调用结构。**不能复制其 `CType=half` 与 elementwise 后处理**，否则已在 max 前损失精度。行归约指令结构可参考 `include/catlass/epilogue/block/block_epilogue_online_softmax_no_mask.hpp:230`、`:419` 的 rowmax 部分；不引入无关 exp、softmax、rescale 功能。

自定义 epilogue 契约：读取某个完整 K dot tile 的 FP32 C；对有效 N 列求每行最大值；将结果合并到该 M-owner/N-shard 的 FP32 rowmax；无效 N lane 为负无穷，无效 M 行不参与输出；跨 N shard 必须先逐行 max，再对 M 求 sum。需要独立的 stateful BMMS policy（拟定义），不能声称现成 `EpilogueAtlasA2ElemWiseNoSource` 已能表达跨 tile rowmax 状态。

## 5. 第一版资源表：可用模板与不能混淆的宏块

初始候选配置仅是待测集合，非最优参数：

| 配置 | L1(M,N,K) | L0(M,N,K) | L1 A+B 双缓冲 | L0A 双缓冲 | L0B 双缓冲 | L0C 单缓冲 | 每 AIC 两槽 GM C |
|---|---|---|---:|---:|---:|---:|---:|
| D0 | 64,128,256 | 64,128,64 | 192 KiB | 16 KiB | 32 KiB | 32 KiB | 64 KiB |
| D1 | 128,128,256 | 128,128,64 | 256 KiB | 32 KiB | 32 KiB | 64 KiB | 128 KiB |
| D2 | 128,256,256 | 128,256,64 | 384 KiB | 32 KiB | 64 KiB | 128 KiB | 256 KiB |

计算：输入 2B，L1=2×2×K1×(M1+N1)，L0A=2×2×M0×K0，L0B=2×2×K0×N0，L0C=4×M1×N1。两槽 GM=2×4×M1×N1。另需 rowmax、最终 partial、同步用空间，不能把此表当作全部 workspace。

D2 的 L0B 和 L0C 正好用满；它在模板资源约束内，但没有新增同区域缓冲余量。若用两 AIV 各承担半行，D2 每 AIV 一份 C 为 64 KiB，双 UB C 为 128 KiB；rowmax、归约 scratch、拷贝尾块 scratch 必须另计后小于 192 KiB。

**不可直接使用**“L1 128×256，L0 64×128”的 Pingpong 配置：固定模板 static_assert 会拒绝。可以将多个同尺寸 BlockMmad task 组成调度宏块，但它本身不会替调用者保留并复用跨调用输入 A，不能把预期复用收益算进去。

后续可研究 `MmadAtlasA2PreloadAsync<...>`，真实定义在 `dispatch_policy.hpp:90`，实现为 `block_mmad_preload_async.hpp`。它有独立 L0C stage 计数和检查（`:99`、`:114`、`:126`），但仍要求 L1/L0 的 M/N 相等（`:128`）。`MmadAtlasA2Preload<bool,bool>` 并不具备这些独立 stage。首轮不要同时更换累加内核、L0C stage、任务顺序和 K shuffle。

## 6. GM 环形槽协议：比模板选型更关键的自定义部分

每个 AIC 有两个独占槽；同组两个 AIV 分割 M 行，任务顺序完全一致：

1. AIC 首次使用空槽不等待；重复使用槽 s 前等待该槽所有消费行片的读取完成通知。
2. AIC 对一个 tile 完成完整 K dot；Fixpipe 写 FP32 GM 后，于 FIX 顺序上发布 READY(s, generation)。
3. AIV 等待 READY，启动 GM→UB 拷贝，只消费自己有效行；**MTE2 拷贝完成后**才发布 FREE。FREE 表示可覆盖 GM，不要求 rowmax 计算已完成；但它对应的 UB 也有独立生命周期。
4. AIV 更新持有 rowmax；N 范围结束后写 rowmax partial，最后依既定固定顺序合并。
5. 最后一轮必须排空所有在途 FIX/MTE2/Vector/GM 写出，最终归约可见性和所有核终止条件必须证明。

官方 `MatmulEpilogue` AIV 在 `blockEpilogue` 调用前执行 `CrossCoreWaitFlagWithReverse`（`:190`），反向 token 只是避免超过 15 次 flag 计数。直接缩减官方 workspace 到两槽会失去正确的消费完成保障。不能在 producer READY 后立即复用，也不能将“收到 READY”当成“读完”。

环形缓冲缩减的是峰值 workspace；所有 C 元素仍需一次 GM 写和一次 GM→UB 读，C 中转总逻辑流量约 8BMN 字节。不能把它写成消除了所有中间结果流量或 Atlas A2 零 GM 融合。

## 7. 泛化和精度边界

- 源码有运行时 actualShape、M/N 对齐处理和 K 尾段长度；这支持设计尾块路线，但不等于已经覆盖本题 M/N 任意、K%8=0 的全部边界。K=40/72/136、M/N 17/65/129、四布局、最后 batch 的 guard 区仍须设备验证。
- 双缓冲替换时特别测试 tile 数 1、2、3、15、16、17，验证冷启动、环回和 flag 计数边界。
- 全 K 保存在 L0C 意味着在 rowmax 前没有额外 K 分片归约；仍是 FP32 dot，并不自动满足题目的 FP64 golden。现有准确性评测必须保留 FP64 dot→max→sum→最终 FP32 的 oracle。
- 禁止用 FP16/BF16 C 中转、TF32、Top-k 抽样等降低问题精度。Split-K 和 shuffle-K 改变求和顺序，若未来尝试，须独立精度门禁；首版不启用跨核 Split-K、atomicAdd 或 K shuffle。
- 两种 dtype、四布局必须从真实 GEMM Copy/Mmad 实例化入手；模板可表达不等于在比赛编译选项下已编译成功。

## 8. 单文件集成的真实成本

`block_mmad.hpp` 是聚合头，会递归引入很多无关模板；`tile_copy.hpp` 还依赖 `tla/tensor.hpp` 及多种 copy/cast 模板。不能仅内联 `block_mmad_pingpong.hpp` 便认为依赖闭合，也不应把整个源码仓塞进 `kernel.asc`。

最小化时应保存固定版本来源、摘录范围和声明依赖表，先保留 A2、FP16/BF16、四布局与 FP32 C 所需类型，再在官方编译入口证明 Host/Device 宏、TPipe 资源、事件 ID 和 entry 的兼容性。若需要评测器不允许修改的 include/link/arch 选项，该 CATLASS 直接集成候选应退出；主路线继续按同一设计的 Ascend C 原生实现，不拖累冲榜进度。

v1.4.0 示例使用 `dav-c220` 族编译设置，与当前项目记载的 `dav-2201` 写法不相同；二者在目标工具链中的映射需实编译确认。也不应把最新版 `CATLASS_ARCH=2201` 宏要求反向误套为 v1.4.0 已存在的要求。

源码许可证文件为 **CANN Open Software License Agreement Version 2.0**，不是 Apache/MIT。复制/修改分发应保留源码通知与协议副本，具体条款以固定仓库 [LICENSE](references/catlass/LICENSE) 原文为准。此项记录实际依赖条件，不替代比赛对第三方代码的规则；当前未见规则明确禁止该来源，但不能据此宣称第三方代码条款已由赛事确认。

## 9. 获得算力后的最小可证伪实验

先验证比赛入口下最小 dense 编译与 FP32 C 路径，再测试一组大 K 的对齐、尾块、四布局和双 dtype。只有通过正确性，才对同机 P01 与 D0 做交错对照，采集设备 task 时间和 Cube/MTE2/FIX/Vector 利用情况。若 D0 在大 K 无收益，判断是 Cube 主体、GM 交接、AIV rowmax 还是核间归约在限制，不立刻展开无方向 tiling 搜索。

单 L0C 的 D0 是可定位差异的起点；D1/D2 用来区分任务粒度、复用/带宽与 occupancy。只有 profiler 显示 FIX↔MMAD 串行空泡显著，才进入 PreloadAsync 的双 L0C；只有 MTE2 成为主要限制，才研究 preload、输入复用与布局专化。没有 NPU 的当前阶段不能宣称任何一项已产生性能提升。

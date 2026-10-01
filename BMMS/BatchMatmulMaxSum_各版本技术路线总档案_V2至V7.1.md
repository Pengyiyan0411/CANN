# BatchMatmulMaxSum 各版本技术路线总档案

> **整理范围：已能定位到源码或原始说明的 V2.0 系列、早期 clean 分支、V3.1，以及本轮 V4—V7.1 全部交付版本。**
>
> **记录截止：V7.1 hybrid 已交付，尚未收到其 Judge 反馈。** 本文依据已有源码、压缩包内 README/AUDIT、题面和本对话截图整理；不引入新的性能实验，不猜测隐藏测试形状，不把后续版本的设计倒写成前一版已经实现的功能。
>
> 文中 `[Sxx]` 是文末的文件来源编号，`[Ixx]` 是评测截图编号。所有截图分数均按显示的耗时复算，不是新测量。源码检查、CPU 模型检查、用户真机反馈分开记载。

## 0. 当前状态：先看这几件事

截至本档案，**有完整 15 点耗时截图且全部通过的主线版本为 V4.3、V5、V7**。其中 V4.3 复算约 **31.1967 分**，V5 约 **27.0361 分**，V7 约 **30.6206 分**。V4 stable-fix 另有用户“这个能过”的反馈，但没有完整耗时表。

V6 `manual_cv` 与 V6.1 均在第 9—12 点失败；这些点显示的耗时不能计为有效加速。V6.2 修复了一个能在 CPU 分组遍历模型中复现的错误，但尚无单独真机反馈。V7.1 是当前最新的模块合并候选，不是已经取得成绩的新基线。

**主线不是单纯地“版本越新越好”，而是几条技术路线交替探索、修补和重新组合：**

- 默认 MIX/KFC 通用矩阵乘路线：V3.1、原 V4、stable-fix、V4.1、V4.2、V4.3、V5。
- AIC 本地 Matmul、手动 AIC/AIV 交接路线：两个 V6 分支、V6.1、V6.2、V7 的通用面板路径。
- 纯 Vector 专用路线：Dot/Tiny 持续保留，V5 增加短点积/PackedTiny/Bank，V7 增加 Resident 和完整合法 K 范围的连续 Skinny。
- 模块混合路线：V7.1 保留 V7 专用 Vector，通用 Matmul 回到 V4.3，并增加安全门与缓冲复用等待。

**最重要的命名区别：**`V6_A2_native` 与 `V6_manual_cv` 是两份不同源码，不是同一文件的两个下载名。后续 V6.1、V6.2 的直接父版本是 `V6_manual_cv`。[S09—S12]

---

## 1. 全部版本共同解决什么问题

### 1.1 数学目标与存储布局

逻辑输入为 `X1[B,M,K]`、`X2[B,K,N]`，输出为 FP32 的 `y[B]`：

\[
C_{bmn}=\sum_{k=0}^{K-1}X1_{bmk}X2_{bkn},\qquad
R_{bm}=\max_{0\le n<N}C_{bmn},\qquad
y_b=\sum_{m=0}^{M-1}R_{bm}.
\]

顺序始终是 **完整 K 点积 → Max(N) → Sum(M)**。不允许改成先沿 M 求和再取最大值，不允许跨 batch 配对。`transposeX1/transposeX2` 仅说明物理存储方式，不改变逻辑计算。[S00]

| 属性 | false 时的存储 | true 时的存储 |
|---|---|---|
| `transposeX1` | `[B,M,K]` | `[B,K,M]` |
| `transposeX2` | `[B,K,N]` | `[B,N,K]` |

各条带/分片中常见的 batch 内起始偏移为：

```cpp
A_offset = transposeX1 ? m0 : m0 * K;
B_offset = transposeX2 ? n0 * K : n0;
```

实际地址还需加上 `batch*M*K` 或 `batch*K*N`。输入原始 M/N/K 决定物理跨度；不能因为把计算切成 `rows × cols`，就随意用局部尺寸替换原始跨度。显式 C 缓冲可以单独指定自己的行跨度。

### 1.2 题面边界与工程边界

题面约束为 `1≤B≤64`、`1≤M,N≤8192`、`32≤K≤8192` 且 K 是 8 的倍数；同时 `BMK≤2^26`、`BNK≤2^26`。输入仅 FP16/BF16，同 dtype、连续 ND，允许负值，不含 NaN/Inf；输出为 FP32。K 点积、Max 与 Sum 要有 FP32 累加或等效精度。[S00]

工程沿用官方 `run_kernel(...)` 接口，提交代码集中在 `code/kernel.asc`。本轮交付一直维持：**一次合法调用只选择一个真实 device kernel launch**；没有 Host 回读输入代算、没有伪造答案、没有跨调用答案缓存。诊断工具和本地 benchmark 不应被当成官方入口的替代物。[S02—S14]

“没有完整 C 矩阵的显式分配”“一次 kernel launch”“完全没有 C 的 GM 流量”是三件不同的事，不能互相替代。

### 1.3 计分与正确性记录方式

题面的计分规则是：15 点全部精度通过后，单点分数为

\[
s_i=\frac{100}{1+\log_{1.5}(t_i/T_i)},\qquad S=\frac1{15}\sum_{i=1}^{15}s_i.
\]

`t_i` 为当前用时，`T_i` 为截图中该点最优用时。每个点权重相同，不是把全部用时相加后算总加速比。[S00]

题面写有 FP32 相对误差 `<1e-4`、绝对误差 `<1e-4`。历史测试程序使用过不同的组合容差。本文保留这一差别：**组合容差通过不自动等于独立绝对/相对门槛均通过；用户某次 Judge 全过也不消除合成扩展测试暴露的边界。** 本文不自行推断 Judge 内部的具体比较表达式。

---

## 2. 阅读技术路线前，统一几个术语

| 术语 | 本档案中的含义 | 容易混淆的地方 |
|---|---|---|
| AIC / Cube | 承担矩阵乘的执行侧 | 不是整个融合算子所有计算都发生在 AIC |
| AIV / Vector | 搬运到 UB 后执行向量计算与归约的执行侧 | 既可能是 Matmul 客户端，也可能只是结果消费者 |
| KFC / 默认 MIX | 本项目旧实现中，由 AIV 发起高阶 Matmul，框架服务侧处理 | `__mix__(1,2)` 本身不说明究竟是谁发起 Matmul |
| AIC 本地 Matmul | `ASCENDC_CUBE_ONLY` 配合 AIC 分支直接调用 Matmul，AIV 独立工作 | 宏需在相关头文件前生效；namespace 不能隔离它 |
| tile / 基本块 | 某一层矩阵乘或向量归约的处理块 | 不一定等于一个完整任务或整个分片 |
| shard / 分片 | 一个 worker 持有的 `(batch,M区间,N区间)` | 内部可能包含多个 M tile 和 N tile |
| stripe / 条带 | 显式 GM 中间结果，例如 `[tileM,nSpan]` | 是有界暂存，不等于完整 `[B,M,N]` |
| panel / packet | 由应用显式指定尺寸的一次较大 Matmul 输出区域 | 内部可以有多个 Matmul 基本块 |
| `partialMax` | 分片的逐行最大值，常见布局 `[B,pN,paddedM]` | 不是最终 batch 分数，也不是先求和后的分片结果 |
| direct | 不需要跨不同计算组汇合的独占情形 | 各版定义不同；不一定连 partial GM 都省掉 |
| `SetDim` | 历史实现中传给 tiler 的核数参数 | 不能单凭它等于 1，就断言外层多核调度一定非法 |

以上术语以本项目实际用法为准。A2 架构与 API 的外部核查记录已保存在各版本的 `SOURCES.md`/`AUDIT.md` 中；本次只是整理这些既有记录，不重新作厂商规格认证。[S05、S09、S13、S14]

---

## 3. 演进关系总图

```text
早期接口与正确性探索
  V2.0 → V2.0.1/.2/.3/.4/.5/.6
       单次 launch、逐 batch、高阶 Matmul、尾块/出块顺序/批次步进
  clean 分支：双 AIV 客户端、Vector 归约、partialMax
                         │
                         ▼
  V3.1：Dot/Tiny + 双 AIV 客户端 + 显式 GM stripe
                         │
                         ▼
  原 V4：shape-aware 选型、N-shard、direct、并行最终归约
          │ 正确性失败
          ▼
  V4 stable-fix：通用路径压到 1AIC+1AIV、固定 16 行
          │ 用户确认能过
          ▼
  V4.1：仍单核，仅将 16 行改为 16/32/64 行
          │ 用户要求恢复竞争力
          ▼
  V4.2：多组 1AIC+1AIV、持久二维分片、显式 GM stripe
          ▼
  V4.3：增加 VECIN Fast，非对齐/拒绝时走 Safe
          │ 15/15，约31.20分
          ├─────────────────────────────────────────────────┐
          ▼                                                 │
  V5：短点积/PackedTiny/Bank + 大 packet 异步双槽             │
          │ 15/15，但约27.04分，整体退步                      │
          ├─────────────────────┐                           │
          ▼                     ▼                           │
  V6 A2_native             V6 manual_cv                     │
  AIC本地、单M条带          AIC本地、整个shard一次setup        │
  N片结束才行归约           每个C基本块先行归约               │
  无独立截图反馈            第9—12点WA                       │
                                ▼                           │
                           V6.1：只改flag编号                │
                                │ 同样9—12点WA               │
                                ▼                           │
                           V6.2：NormTileCursor              │
                                │ CPU反例修复，无独立真机反馈 │
                                ▼                           │
  V7：Resident/Skinny + 显式面板，不解码内部tile顺序          │
          │ 15/15，约30.62分，局部大幅改善                    │
          │                                                 │
          └──── Resident/Skinny ──────┐      Dot/Tiny/通用 ──┘
                                      ▼
                           V7.1 hybrid
                           + FlatFastStream 安全门
                           + MTE3_V 生命周期等待
                           尚无新Judge反馈
```

图中的箭头表示技术继承与本轮讨论的演进，不代替 Git commit 血缘。尤其 `clean` 与 V3.1 的准确提交父子关系、两份 V6 的开发先后细节，不能仅由文件名完全恢复。

---

## 4. 版本索引：一眼看清每版解决的主问题

| 版本 | 技术路线的主要变化 | 通用路径拓扑 | 已有反馈 / 定位 |
|---|---|---|---|
| V2.0 系列 | 接口、尾块、出块顺序、batch 步进 | 默认 MIX(1,1)，主要按 batch 分工 | 早期正确性探索；没有完整逐版成绩链 |
| clean 分支 | Dot + Vector 行归约 + N 分片 | 默认 MIX(1,2) | 早期实现素材；不能当最新稳定版 |
| V3.1 | 增加 Tiny，采用显式 GM stripe 避免 VECIN pitch 推断 | 默认 MIX(1,2) | 同计算代码出现过不同正确性反馈 |
| 原 V4 | 未标定代价模型、二维任务、direct、N读块错位、并行Finish | 默认 MIX(1,2) | 前两点通过，通用路径大面积 WA |
| V4 stable-fix | 单组、单 worker、无跨核 N 分片、补 fence | MIX(1,1)，全局1组 | 用户确认能过；性能隔离版 |
| V4.1 | 单核不变，M条带16→16/32/64 | MIX(1,1)，全局1组 | 没有独立成绩，用户否定渐进幅度 |
| V4.2 | 多组恢复、persistent shard、显式 GM stripe | 默认 MIX(1,1)，多组 | 用户反馈性能差；没有完整表 |
| V4.3 | VECIN Fast + Safe，整 shard 一次 setup | 默认 MIX(1,1)，多组 | 15/15，31.1967分 |
| V5 | 新Vector专用分支 + 异步大packet双槽 | 默认 MIX(1,1)；Bank另用Vector | 15/15，27.0361分 |
| V6 A2_native | AIC本地单M条带，双AIV，N片结束行归约 | 手动 MIX(1,2) | 与后一个V6不同；无独立评测绑定 |
| V6 manual_cv | 整shard本地Matmul，双AIV消费基本块 | 手动 MIX(1,2) | 11/15，第9—12点WA |
| V6.1 | READY/FREE移到4—7 | 同manual_cv | 同样11/15，flag假说未修好故障 |
| V6.2 | 消费者解码stepM/stepN/iterateOrder | 同manual_cv | 模型反例修复；无独立Judge反馈 |
| V7 | Resident、全合法K连续Skinny、显式面板、延后行归约 | 专用Vector + 手动MIX(1,2) | 15/15，30.6206分 |
| V7.1 | V7专用Vector + V4.3通用模块，新增安全门 | 默认MIX(1,1)，Skinny为MIX(0,1) | 最新待设备验收合并候选 |

---

## 5. 前史：V2.0 系列、clean 分支与 V3.1

### 5.1 V2.0—V2.0.6：先建立单次 launch 的正确性骨架

共同路线为：一个计算组持有一个 batch 的完整矩阵乘，`Iterate/GetTensorC` 取回 C tile，在 UB 中逐行处理，再输出一个 `y[b]`。早期行最大值与最终累加含标量 `GetValue/SetValue` 操作，不是后面整块 Vector 归约的高吞吐实现。输出标量采用 UB→GM 精确四字节拷贝的设计已出现在这组早期源码中。[E00—E06]

```text
单个batch
  → 高阶Matmul迭代C tile
  → VECIN局部结果
  → 标量行max / 行最大值保存
  → batchSum
  → 四字节DMA写y[b]
```

| 子版本 | 从已定位源码能确认的变化 |
|---|---|
| V2.0 | 初始单launch正确性实现，Host使用`MatmulApiTiling`；不能据注释把目标环境兼容性当作已认证 |
| V2.0.1 | 改用`MultiCoreMatmulTiling`，`SetDim(1)`、完整single shape；设备显式`SetTail(M,N,K)`；仍把行stride当作baseN |
| V2.0.2 | 当前定位文件移除设备显式SetTail，按compact尾块用`r*curN`寻址；这是实际文件差异，不只由版本名推断 |
| V2.0.3 | 文件名为stridefix，保留`r*curN`，但设备`SetTail`又存在；不把它和V2.0.2视作所有改动单向累积 |
| V2.0.4 | ceil-base策略：小于等于16/32/64的尺寸采用相应向上覆盖的基本块，避免小尾块产生不必要迭代 |
| V2.0.5 | 根据当时观察修正FIRSTN出块理解，使用全M的rowMax保存跨N块结果；但当时的平坦顺序认识不能扩展为所有Norm分组配置 |
| V2.0.6 | 启动组数不超过可用AIC组数；通过`batchIdx += launchBlocks`循环处理B大于组数的情况 |

**这一阶段的价值**是逐步暴露：API可用性、C尾块行跨度、tile顺序、batch分工与标量输出缓存行问题。它们是后续重构的背景，不代表每个命名版本都已通过完整15点评测。

资料中还存在早期 S3d / Q1 等探针引用和 v0.x 诊断记录。本次没有形成这些探针全部源码与结果的完整对应，因此不额外编造一张 V0/V1 逐号成绩表。

### 5.2 `batchmatmulmaxsum_submit_clean.asc`：从标量归约转到分块 Vector

该文件没有与本轮 V4 以后同样清楚的版本编号，本文按文件名独立保存。[E07]

其通用 `FusedDevice` 使用 VECIN 结果，任务为 `(batch,M tile,N shard)`，每个任务只有一个应用M块；N不足以提供完整负载时可跨AIV分片。先对不同N块的同列lane做逐元素Max，再横向`WholeReduceMax`，写入 `partialMax`；全AIV屏障后由worker 0汇总。

入口为默认 `__mix__(1,2)`：这里两个AIV是Matmul发起侧，而不是后续V6中的“同一个C块的两个纯消费者”。源码已有Dot快路径，尚不是V3.1的完整Dot/Tiny组合。尾块VECIN行跨度在该分支的注释/索引中带有固定baseN假设；不能据“clean”命名认定这个假设普适。

### 5.3 V3.1：显式 GM stripe + Dot/Tiny

**核心目的：**不再让应用侧依赖 `GetTensorC` 的 VECIN 尾块行跨度，通用 Matmul 改为输出一个 worker 私有的显式 GM 条带，再由 Vector 按明确跨度搬运。[S01]

```text
Dot / Tiny：独立Vector kernel
通用：AIV调用Matmul → GM stripe[baseM,nSpan]
                   → UB按baseN搬运
                   → lane-wise Max → 行Max
                   → partialMax[B,nSplits,paddedM]
                   → SyncAll → worker0最终Max/Sum
```

计划中 `baseM` 从16/32/64选择；优先用B/M任务填核，不足时增加N分片；`baseN`最高128。`blocks=ceil(tasks/2)`后限制在可用AIC组数内，`workers=2*blocks`。Matmul的`SetDim(1)`描述单次局部计算，外层手工调度不同任务。

**已知稳定性问题：**原审计比较409380/409737，确认计算代码一致，区别仅是文件末尾换行，且其他7个文件相同。历史上存在全过与仅前两点通过两种结果；因此不能拿一次通过把它封为稳定基线。Host tiling或分配失败会静默返回，部分同步/释放错误码未处理，属于明确诊断缺口；是否实际触发，资料没有证明。[S01a]

原工程`run.sh`只测`(1,1,1,32)`的FP16 Dot，不能为通用Matmul作正确性背书。[S01a]

**字节版本注意：**本次容器中的`kernel_v3_1.asc`为26160字节、无末尾LF，对应旧审计409737的哈希。旧审计记载的409380版为26161字节。两者不能混用“逐字节相同”的说法，但审计确认计算内容相同。

---

## 6. V4 系列：二维调度、稳定性隔离与恢复多核

### 6.1 V4 方案文档：目标远多于真正落地的项目

`BatchMatmulMaxSum_V4_终极冲榜方案.md`提出的是形状分类、多kernel选择、二维M/N分核、L1驻留、静态K、MDL/BasicBlock、布局优化等候选集合，而不是已经实现所有功能的提交代码。[S02a]

**档案中必须分开：**“V4方案里提到过”“某份源码已有入口”“实际进入过该入口”“测得比旧版快”。后续很多版本只是实现了其中一部分，未形成离线真机autotune表。

### 6.2 原 V4：在 V3.1 骨架上扩大规划空间

原文件为`BatchMatmulMaxSum_V4_kernel.asc`。[S02]

**保留路线：**默认MIX(1,2)、显式GM stripe、FP32 Vector归约、Dot/Tiny。

**新增内容：**

- 枚举`baseM∈{16,32,64}`、`baseN∈{16,32,64,128}`和N分片。
- 用未实测标定的解析代价项综合计算量、输入重复读取、C流量、任务开销、partial合并及workspace。
- 一个任务独占整个batch时，`direct`直接归约输出，跳过partial和全核汇合。
- N只分一片时，对不同worker的N tile读取起点作错位；改变的是读取顺序，不是数学覆盖。
- 多个batch的最终归约按worker并行，取代全由worker0收尾。

此时`direct`条件是**只有一个M tile且一个N分片**，不同于V4.2“一个持久worker可遍历多个M tile但仍独占整个batch”。

**结果：**用户截图表现为第1/2点通过、后续大面积100% WA。这个结果支持优先检查通用路径，但不能从测试编号反推出每点具体分支。

当时曾将`SetDim(1)`与MIX多AIV不匹配视作根因；后续V4.2审计明确撤回“仅凭该数字就能证明错误”的论断。该次故障没有被单变量复现实验唯一定位。[S05]

### 6.3 V4 stable-fix：牺牲吞吐，隔离通用路径

文件为`BatchMatmulMaxSum_V4_stable_fix_kernel.asc`。[S03]

通用路径固定成：

```text
__mix__(1,1)
blocks = workers = 1
SetDim(1)
baseM = 16
baseN = 16 / 32 / 64
nSplits = 1
nSpan = N
```

同一个AIV顺序处理所有batch和M条带；使用显式C跨度，逐行max写入partial；最后一次固定顺序Sum。去掉跨核`SyncAll`，换成本核`MTE3_MTE2`依赖，并保留最终归约后的`V_MTE2`复用等待。Dot/Tiny保持原并行实现。

**用户反馈：**“这个能过，继续”。这是通用路径的隔离成功证据，但同时改了核拓扑、核数、N分片、tile和同步，不能据此证明究竟是哪一项修好了原V4。

### 6.4 V4.1 conservative：只扩大 M 条带

文件为`BatchMatmulMaxSum_V4_1_conservative_kernel.asc`。[S04]

与stable-fix的代码差异集中在：

```cpp
baseM = M <= 16 ? 16 : (M <= 32 ? 32 : 64);
```

其余通用单组MIX(1,1)、无N跨核分片、同步与归约保持不变。大M时Matmul调用次数可减少，但没有恢复多核吞吐。

**反馈：**用户认为推进幅度太小，要求回到原先有竞争力的多核路线。没有独立的完整评测表，不能为其填写新成绩。

### 6.5 V4.2 multicore：恢复多组 MIX(1,1) 的二维 persistent shard

文件为`BatchMatmulMaxSum_V4_2_multicore_kernel.asc`。[S05]

**不是单核版。**每组1AIC+1AIV，启动`min(availableCoreNum,B*pM*pN)`组；一个worker持久处理完整矩形shard，内部连续遍历M条带。

```text
Host选 tileM / vecN / pM / pN
 → worker持有(batch,mShard,nShard)
 → 对每个M tile做同步IterateAll到私有GM stripe
 → 搬运到UB，先lane-wise Max，再行Max
 → direct：全batch行max常驻UB，直接输出
 → 非direct：partialMax → 全AIV屏障 → 按batch并行最终归约
```

M/N按tile编号的整数前缀区间切分，N任务有对角置换，以保持覆盖且分散同时读取位置。tileM最高128、vecN最高256，实际组合受应用UB约束。Host仍采用未拟合的成本模型。[S05]

`SetDim(p.workers)`提供发起侧预算，`SetSingleShape`固定单次完整工作，返回tiling必须覆盖该工作；它不是把外层一个任务又切成多个未知子任务。通用入口增加`__schedmode__(1)`，并保留private C、partial发布、merged UB复用的等待。

**反馈：**后续用户认为性能仍差；没有独立15点截图可填写。只能记“恢复了多核技术路线”，不能记“相对上一版实测提高多少”。

### 6.6 V4.3 vecin_fast：Fast/Safe 双路通用计算

文件为`kernel_v4_3.asc`。[S06]

**Fast路：**C类型切为VECIN，`Iterate<true>()`后`GetTensorC<true>(...,0,true)`，应用侧接收一个基本块并在线行归约。每个完整shard只做一次Matmul setup/End。主要限制为N按所选vecN整齐划分，均匀N分片；M尾块可以缩小有效行。

**Safe路：**N不对齐、Fast规划/tiling不适用时，继续采用V4.2类型的显式GM stripe和确定行跨度。Dot/Tiny不变。

Fast规划枚举M/N基本块与二维网格，应用C缓冲允许最高16384个float，额外预算约97KiB；这些是代码里的预算，不是新做的设备资源认证。

**关键历史更正：**当时README称Fast“消除了C的GM往返”。后续审计已指出，VECIN是接口层位置，不能据此认定A2底层没有GM中转。因此准确表述是：**Fast没有应用显式分配的C stripe；底层传输不能仅由LocalTensor返回形式下结论。**旧README中的512MiB“直接消掉”说法不应再当作既定性能事实。[S06、S13]

**另一个后续发现的边界：**Fast消费者把FIRSTN当成全分片平坦M-fast序列，并未处理一般Norm分组。V7.1为此增加接受条件；V4.3曾15/15，不意味着所有合法形状都已排除这一风险。

**反馈：**15/15，截图复算31.1967分，是已有完整成绩记录中最强的单份基线。[I01]

---

## 7. V5 pipeline：增加专用 Vector，并改成大 packet 异步交叠

文件为`BatchMatmulMaxSum_V5_pipeline_kernel.asc`。[S08]

### 7.1 专用入口与通用入口

| 路径 | 触发/计算方式 | 相对V4.3的变化 |
|---|---|---|
| Dot | M=N=1；K≤64使用`WholeReduceSum`短点积 | 包含40/48/56，不限二次幂 |
| PackedTiny | 原Tiny范围且K是32—1024内二次幂 | 一次批量计算多个N点积，Block/WholeReduce组合 |
| 原Tiny | Tiny范围中的其余K | 保留旧实现 |
| BankDot | M=1或N=1，且K是32—1024内二次幂 | 连续bank直接搬运；`[K,L]`形式先合并搬运再Gather |
| Packet | 其余通用矩阵 | 默认MIX(1,1)，每worker双GM槽 |

Bank先完成每条向量的整个K点积，N=1再Sum(M)，M=1再Max(N)。不是跨核K分段求和。V5的Bank入口当时仍写为`__vector__`而其内部使用全AIV屏障；后续V7连续Skinny明确改用`__mix__(0,1)`。前者应视作该历史代码的潜在兼容性点，不能凭一轮15/15推广为所有场景的通用范式。

### 7.2 大 packet 路线

V5不用V4.3的逐基本块VECIN消费，而将一次Matmul扩大为显式GM packet。典型上限：K≤256时最高256×1024；较大K时通常最高128×512；非常窄N存在最高512行的分支。均受实际分片和workspace限制。

```text
Start packet0
Wait0 → End0 → Start packet1 → Vector归约packet0
Wait1 → End1 → Start packet2 → Vector归约packet1
……
```

调用`IterateAll<false>(...,0,false,true)`，再`WaitIterateAll()`；每个Matmul对象最多一个未完成请求。另一个GM槽可由Cube写入，Vector读取上一槽。C的行跨度显式为`packN`，因此尾块不需要依赖基本块流顺序。

规划从“貌似微秒”的浮点成本模型改为整数结构排序：最重分片的填充工作量、使用核数、输入重复读取。不是实测autotune。

### 7.3 结果与不能推出的结论

V5仍然15/15，但复算27.0361分，低于V4.3的31.1967分；15点中13点变慢。[I01、I02]

这证明**该整体组合在这两次截图对比中退步**。不能据此单独断言是异步API、packet尺寸、Bank转换、固定tile还是调度中的某一项导致；没有逐shape路径日志和消融数据。

其输出到GM的总C搬运仍存在。扩大packet、减少消息次数、双缓冲交叠是目标，不是得到提速的充分条件。

---

## 8. V6：两份不同源码必须分别保存

### 8.1 V6 `A2_native`：单 M 条带本地 Matmul

文件为`BatchMatmulMaxSum_V6_A2_native_kernel.asc`，与后一个`manual_cv`不同。[S09]

**核心变化：**头文件前定义`ASCENDC_CUBE_ONLY`，Matmul只在AIC分支创建和执行；每组两个AIV读取同一个C块的不同M行。它们不再各自发起一份Matmul。

```text
一个shard
  for 每个M条带：
    SetSingleShape(不超过一个baseM, 整个N分片, K)
    Iterate/GetTensorC按N输出紧凑C块
    双AIV逐块lane-wise Max
    N片结束后才WholeReduceMax
```

这里单次Matmul只包含一个M基本块，避免多M块顺序解码。代价是每个M条带都做一次setup/End。默认小K选择最高128×256基本块，大K选择最高64×128；二维网格按核占用、重复读取和最重分片等整数指标选型。

两槽环形协议从这份源码开始已经使用`READY=4/5`、`FREE=6/7`、`PAIR_DONE=8`。所以不能把后面“V6.1才改到4/5”的历史套到这个文件。

**这一分支确实实现了沿N片延后横向行归约。**它不是后一个manual_cv的逐块行归约实现。

**状态：**材料中没有能单独绑定这份源码的Judge截图；不能把manual_cv的11/15结果贴到它身上，也不能认为它已15/15。该包AUDIT记录的CPU最大绝对差为`2.44140625e-4`，在其组合容差下通过；不能将另一份V6报告的更小误差数字移用到这里。

### 8.2 V6 `manual_cv`：整 shard 本地 Matmul + 双消费者

文件为`BatchMatmulMaxSum_V6_manual_cv_kernel.asc`，是后续V6.1和V6.2的父实现。[S10]

为减少反复setup，这一版把Matmul调用范围扩大到整个M/N shard，内部存在多个M和N基本块。生产者`Iterate/GetTensorC`返回紧凑ND块，写入每组的两个GM槽；两个AIV各自读取一半M行。

| 与A2_native相比 | manual_cv实际行为 |
|---|---|
| Matmul setup/End | 每整个shard一次，而不是每个M条带一次 |
| M/N块坐标 | 消费者起初写死为N外、M内的平坦顺序 |
| 行最大值保存 | 每个C块先横向行归约，再更新完整M方向的running row max |
| UB C缓冲 | 两个独立局部输入队列c0/c1 |
| 初始flag | READY 0/1、FREE 2/3、PAIR_DONE 8 |
| 默认块大小 | K<512时M最高64、N最高256；K≥512时通常最高128×128，并可为核占用缩小 |

**重要：manual_cv没有实现“全部N块到齐才做一次行归约”。**此前某些说明把A2_native的设计混到了manual_cv，后续V7重评已纠正。

生命周期上，AIC在复用某个GM槽前等待两个AIV的FREE；AIV完成MTE2读取就归还槽，之后继续使用自己的UB副本；即使某个AIV在M尾块没有有效行也必须应答。退出时排空最后一个/两个未消费归还标志。

最终direct仍要汇合两个AIV的行最大值，使用pair-local屏障；它不等同于V4.2那种完全省掉partial GM的direct。

**反馈：**按交付顺序对应的截图为11/15，第9—12点全部WA。通过点3/4/5/13/14等比V4.3快，但失败点更短的耗时不记作有效提速。[I03]

### 8.3 V6.1 flagfix：可证伪的最小改动，结果没有修好

源码存于`BatchMatmulMaxSum_V6_1_flagfix.zip`的`kernel.asc`。[S11]

```text
manual_cv原版：READY 0/1，FREE 2/3，PAIR_DONE 8
V6.1：        READY 4/5，FREE 6/7，PAIR_DONE 8
```

只修改两个flag基址及解释注释，不改Matmul、分片、归约、存储布局、workspace与launch。原假说是规避文档所述高阶API内部保留编号。

**实验反馈：**第9—12点仍WA，依然11/15。[I04]

因此历史结论应该是：**编号隔离作为防御性设计保留，但“改flag就能修复当前故障”的假说未获支持。**不能继续把它说成已经坐实的根因；也不能把第一次解释中“很确信”的措辞当证据。

### 8.4 V6.2 tileorder_fix：按实际 Norm 分组顺序解码

文件为`BatchMatmulMaxSum_V6_2_tileorder_fix_kernel.asc`。[S12]

发现的问题是：`FIRSTN`不等于所有配置都按整个shard平坦遍历。Norm中还有由stepM/stepN控制的内外分组，消费者原先只根据接收序号推断 `(mt,nt)`，可能认错矩阵块。

以4个M块、2个N块、`stepM=2`为例：

```text
旧消费者假设：
(M0,N0) (M1,N0) (M2,N0) (M3,N0) (M0,N1) (M1,N1) (M2,N1) (M3,N1)

分组顺序模型：
(M0,N0) (M1,N0) (M0,N1) (M1,N1) (M2,N0) (M3,N0) (M2,N1) (M3,N1)
```

V6.2把实际返回`TCubeTiling`交给消费者，新增`NormTileCursor`，利用`iterateOrder`和`stepM/stepN`解码；短组也按实际范围处理。随后用正确块坐标决定真实行列、初始化位置和最终发布时机。

**独立反例：**包内记录同一组结构化输入的参考输出1664，旧V6.1函数体在分组生产者模型下输出2272，新V6.2输出1664。这比“再改一个参数试试”更强，证明旧源码确实存在可复现的块归属缺陷。[S12的`reports/legacy_reproduction.json`与`fixed_reproduction.json`]

但这个模型只针对声明的默认Norm范围，不能推广成任意MDL/BasicBlock的迭代规则。也没有隐藏9—12点的真实tiling，不能宣称已证明这四点唯一根因。**截至V7.1交付，V6.2仍没有独立Judge反馈。**

---

## 9. V7：分输入家族 + 显式面板，摆脱基本块顺序协议

文件为`BatchMatmulMaxSum_V7_kernel.asc`。[S13]

### 9.1 路由顺序

```text
M=N=1 → 原Dot
否则命中原Tiny → 原Tiny
否则命中Resident → Resident Vector
否则命中连续Skinny → Skinny Vector
否则 → AIC本地显式Panel
```

Dot/Tiny函数体沿用V4.3。V7不是第一次提出多路径——V4方案和V5已经有类似目标——它的变化是重新定义路径覆盖和通用交接契约。

### 9.2 Resident：小矩阵整份输入常驻 UB

条件同时满足：

```text
M ≤ 32，N ≤ 64，K ≤ 128
MN ≤ 256
MNK ≤ 16384
(M+N)K ≤ 8192
并且不属于更优先的原Tiny范围
```

每个batch把两份输入一次搬入UB，按四种物理布局Gather成连续K向量，K补到最高128的二次幂；对某一M行批量计算所有N点积，再Max，最后Sum。没有Matmul对象、Matmul tiling、用户workspace或跨核屏障。

这些阈值是已实现的候选范围，**不是实测得出的全局最优分界**。代码没有通过测试点编号选择它。

### 9.3 Skinny：连续bank支持所有合法 K

条件为：

```text
N=1 且 transposeX1=false    // A bank为[M,K]
或
M=1 且 transposeX2=true     // B bank为[N,K]
```

对全部合法K都适用，不再限制二次幂K≤1024。每个点积仍完整计算K；N=1最终Sum行点积，M=1最终Max列点积。非连续`[K,L]`存储不强行在Vector转置，交给通用Panel。

工作块大小为`chunk=min(16,8192/kp)`，其中`kp=ceil(K/16)*16`。较长bank分配给多个AIV，独立写点积partial，再固定归约。需要全AIV屏障的入口明确使用`__mix__(0,1)`；短bank的direct情形不分配partial。

### 9.4 通用 Panel：整面板显式 row pitch

V7仍是AIC本地Matmul，默认手动MIX(1,2)，但不再把SDK内部基本块流暴露给消费者：

```cpp
SetOrgShape(M, N, K, K, panelN);
SetTensorA(...);
SetTensorB(...);
SetSingleShape(realRows, realCols, K);
IterateAll<true>(slot, 0, false);
End();
```

生产者完成一个指定尺寸的完整面板，C行跨度固定为`panelN`；内部无论先算哪个base块，消费者都按显式二维地址读取。删掉`NormTileCursor`依赖。

默认K≤128时最高64×512，其他K最高128×256；失败时有较小面板fallback。规划优先用B/M行任务分核，不足时再切N；不是V6的全二维网格搜索。

每个AIV持有自己的M半区：先对全部N面板做lane-wise Max，最后才做一次横向行归约。两槽GM与一个应用UB输入队列的生命周期分开管理；FREE在MTE2读取结束后返回，Vector继续处理UB副本。

### 9.5 正确性收益与性能代价一起记录

显式面板减少了跨核协议对私有遍历规则的依赖，但代价是**每面板一次setup/End**，可能丢失跨面板的输入/L1复用。优先B/M的分片也可能增加大N下相同B矩阵的重复读取。原重评文档把这些列作代价，没有证明它们就是全部退化的唯一原因。

用户随后提交的完整截图为15/15，复算30.6206分；这是对最初README“未收到真机”的状态更新，而不是删除README当时的事实。[I05]

相比V4.3，V7的第3/4/15点用时分别为5.24/6.44/29.38μs，改善明显；第8/11/12点却为156.21/284.19/244.43μs，明显退化。总体7点更快、8点更慢。

**不能据截图把每个改善点确定归因到Resident/Skinny/Panel。**没有真实shape与分支日志，某些改善可能来自Panel；这正是V7.1选择性合并仍有不确定性的原因。

扩展CPU测试另记录4个输出超过独立绝对误差门槛，最大`2.44140625e-4`，来自FP16、`(1,8192,1,32)`、A转置、全负模式。它们满足组合容差，不是NPU失败截图。Judge15/15与这个模型边界同时保留。[S13/AUDIT]

---

## 10. V7.1 hybrid：按模块合并，而不是按测试点拼成绩

文件为`BatchMatmulMaxSum_V7_1_hybrid_kernel.asc`，当前最新交付。[S14]

### 10.1 保留与移除清单

| 模块 | 来源 / 是否保留 |
|---|---|
| Dot | V4.3，保留 |
| 原Tiny | V4.3，保留 |
| Resident | V7，函数体、条件和优先级保留 |
| 连续Skinny + FinishMax + MakeSkinny | V7，保留 |
| 通用Fast/Safe与主要规划器 | V4.3，恢复 |
| V7 PanelProducer/PanelConsumer | 不并入 |
| V6.2 NormTileCursor | 不并入 |
| ASCENDC_CUBE_ONLY | 不定义；整个文件保持默认MIX/KFC模式 |

**为何不直接把V7和V4.3的文件串接？**二者Matmul编译模式不同，宏在头文件解析时生效，不由运行时条件或namespace决定。本版只移植V7中不创建Matmul对象的Vector模块，避免重置SDK include guard或引入私有类型来混装。

因此V7.1是**V7专用Vector + V4.3通用Matmul**，不是“V7所有快点 + V4.3所有快点”。

### 10.2 Fast 安全门：不解码复杂序列，只接受已符合旧假设的序列

旧V4.3 Fast仍要求全分片的平坦N外/M内顺序。V7.1在接受tiling时加入：

```cpp
maxMTiles = ceil(mTiles / pM);
nTilesLocal = nTiles / pN;

FlatFastStream =
    maxMTiles <= 1 ||
    nTilesLocal <= 1 ||
    (iterateOrder == 1 && stepM >= maxMTiles);
```

此外检查stepM/stepN为正、iterateOrder合法。不满足时用原显式GM-stripe Safe，不进入脆弱Fast。

这里采用的是**缩小Fast合法域**，不是把V6.2的全Norm游标合并进去。这也意味着某些原先进入Fast的配置会回退，不能保证通用部分耗时逐指令等同旧V4.3。

### 10.3 缓冲区生命周期补丁

Fast路径把非队列running buffer写入partialMax后新增`MTE3_V`等待，避免下一任务提前覆盖仍被MTE3读取的UB。数值函数和主要规划逻辑不变。

原包审计记录17个关键函数/类/规划块按来源逐字节核对。本次档案复核文件身份与上述关键路径，没有重新执行该包全部CPU测试。

### 10.4 当前证据与限制

V4.3和V7各自有15/15反馈；**V7.1尚无Bisheng/A2/Judge新结果**。来源函数各自通过，不等于新组合的编译、路由、回退与生命周期已被真机确认。

两张截图逐点取更快耗时，可得35.0815分；它只是假想拼接参照，不是V7.1成绩、不保证值，也不是理论性能上限。

V7.1完整CPU测试另记录12个独立绝对误差门槛失败输出，最大`1.220703125e-4`，同样集中在合成的全负`(1,8192,1,32)`用例，涉及继承的Skinny和Safe数值路径。原包明确保留这些记录。[S14/AUDIT]

---

## 11. 横向对照：真正改变的是哪些维度

### 11.1 通用 Matmul 的“谁发起、一次算多大、怎么交接”

| 路线 | Matmul发起侧 | 一次setup覆盖 | 应用层C交接 | 消费者需知道SDK出块顺序吗 |
|---|---|---|---|---|
| V2.0系列 | 默认MIX高阶路径 | 主要为完整batch | VECIN tile | 需要，当时有错误假设 |
| V3.1 / 原V4 / stable / V4.1 | AIV客户端 | 一个M tile×N shard | 显式GM stripe | 不需要解码C基本块顺序 |
| V4.2 | AIV客户端 | 持久任务内每个M tile×N shard | 显式GM stripe | 不需要 |
| V4.3 Fast | AIV客户端 | 整个shard | GetTensorC至VECIN | 需要平坦顺序假设 |
| V4.3 Safe | AIV客户端 | 一个M tile×N shard | 显式GM stripe | 不需要 |
| V5 Packet | AIV客户端 | 一个较大packet | 显式双GM槽 | 不需要 |
| V6 A2_native | AIC本地 | 一个M基本块×整个N shard | 紧凑基本块双槽 | 单M条带规避多M分组问题 |
| V6 manual_cv / V6.1 | AIC本地 | 整个shard | 紧凑基本块双槽 | 需要；起初假设错误 |
| V6.2 | AIC本地 | 整个shard | 同上 | 用NormTileCursor解码 |
| V7 Panel | AIC本地 | 一个显式panel | 固定panelN跨度双槽 | 不需要 |
| V7.1 通用 | AIV客户端 | 继承V4.3 | Fast/Safe | Fast设安全门；否则Safe |

### 11.2 行归约时机

| 版本/路径 | 每个C块先横向RowMax | 所有N块到齐后才横向RowMax |
|---|---|---|
| V3.1、原V4、stable、V4.1、V4.2 | 否 | 是，在当前M条带/N分片内先lane-wise Max |
| V4.3 Fast | 是 | 否，逐块行max更新running[M] |
| V4.3 Safe | 否 | 是 |
| V5 Packet | 是，按Vector读取子块 | 否 |
| V6 A2_native | 否 | 是，单M条带内 |
| V6 manual_cv、V6.1、V6.2 | 是 | 否 |
| V7 Panel | 否 | 是，明确的M任务内 |
| V7.1 | 由继承分支决定 | 由继承分支决定 |

“延后行归约”并不是V7首次提出或首次出现在所有源码中；它在早期显式stripe和V6 A2_native等分支已经存在。真正需要纠正的是：不能把它归到实际仍逐块归约的V6 manual_cv/V6.2上。

### 11.3 专用路径覆盖

| 特化 | 最早能定位的相关实现 | 后续变化 |
|---|---|---|
| M=N=1 Dot | clean / V3.1等早期源码 | 多版保留；V5加短K替代，V6/V7/V7.1恢复V4.3函数体 |
| Tiny一般小矩阵 | V3.1 | M*N≤16、K≤1024、MNK≤8192；四种布局 |
| PackedTiny | V5 | 仅二次幂K；后续未作为通用保留模块 |
| 连续与转置Bank | V5 | M=1或N=1，二次幂K≤1024；转置用Gather |
| Resident | V7 | 全输入UB常驻的稍大小矩阵；V7.1完整继承 |
| 全合法K连续Skinny | V7 | 只选真正[L,K]连续bank；V7.1完整继承 |
| BasicBlock/MDL/IBShare/低阶Mmad | 方案与重评中的候选 | 截至V7.1未作为主线已交付优化标记完成 |

---

## 12. 历史性能原始表与复算

### 12.1 完整截图数据

单位均为μs。V6/6.1的`†`标记表示该点WA，**不能拿来计算有效分数或有效加速比**。“100%输出错误占比”表示全部输出未通过比较，不表示数值相对误差恰好为100%。表中的V6专指`manual_cv`。映射根据对话中的交付顺序与用户反馈建立；截图没有同时附源码哈希，不能伪称已经完成评测二进制强绑定。

| 点 | 最优T | V4.3 | V5 | V6 manual_cv | V6.1 | V7 |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1.22 | 2.50 | 2.61 | 2.45 | 2.37 | 2.80 |
| 2 | 1.58 | 5.44 | 5.98 | 5.44 | 5.58 | 6.00 |
| 3 | 2.16 | 10.19 | 9.89 | 7.75 | 7.93 | 5.24 |
| 4 | 2.92 | 11.62 | 12.02 | 9.70 | 10.16 | 6.44 |
| 5 | 3.62 | 9.62 | 9.97 | 8.61 | 8.88 | 8.61 |
| 6 | 7.23 | 14.28 | 15.41 | 15.99 | 16.12 | 15.01 |
| 7 | 5.70 | 13.20 | 13.80 | 12.74 | 13.81 | 12.87 |
| 8 | 17.32 | 90.43 | 120.91 | 89.49 | 91.68 | 156.21 |
| 9 | 52.01 | 119.96 | 161.28 | 88.61 † | 89.77 † | 127.73 |
| 10 | 72.47 | 140.55 | 139.14 | 110.93 † | 112.90 † | 171.77 |
| 11 | 74.82 | 169.95 | 237.81 | 126.65 † | 129.41 † | 284.19 |
| 12 | 91.20 | 110.15 | 168.84 | 134.01 † | 136.07 † | 244.43 |
| 13 | 9.37 | 26.66 | 42.70 | 21.48 | 22.76 | 21.43 |
| 14 | 10.11 | 24.95 | 30.84 | 20.55 | 22.47 | 15.81 |
| 15 | 9.04 | 110.28 | 113.71 | 112.51 | 110.29 | 29.38 |

### 12.2 成绩与逐点拼接参照

| 版本/组合 | 正确性资格 | 复算平均分 |
|---|---|---:|
| V4.3 | 15/15 | 31.19669 |
| V5 | 15/15 | 27.03606 |
| V6 manual_cv | 11/15，不计分 | — |
| V6.1 | 11/15，不计分 | — |
| V7 | 15/15 | 30.62064 |
| V6.2 | 无单独反馈 | — |
| V7.1 | 尚无反馈 | — |
| V4.3/V7逐点较小值 | 假想组合，不是一次真实提交 | 35.08148 |

V7相对V4.3改善的点是3、4、5、7、13、14、15；其余8点较慢。第15点从110.28降到29.38μs，但第8点从90.43升到156.21μs，第12点从110.15升到244.43μs。这是V7.1采取模块合并而非全面替换的直接背景。

逐点拼接表仅包含两份都全过的V4.3与V7，不使用V6/6.1的失败耗时：

| 点 | 取自 | 较小耗时 | 对应单点分数 |
|---:|---|---:|---:|
| 1 | V4.3 | 2.50 | 36.1086 |
| 2 | V4.3 | 5.44 | 24.6961 |
| 3 | V7 | 5.24 | 31.3906 |
| 4 | V7 | 6.44 | 33.8901 |
| 5 | V7 | 8.61 | 31.8783 |
| 6 | V4.3 | 14.28 | 37.3327 |
| 7 | V7 | 12.87 | 33.2376 |
| 8 | V4.3 | 90.43 | 19.7002 |
| 9 | V4.3 | 119.96 | 32.6675 |
| 10 | V4.3 | 140.55 | 37.9700 |
| 11 | V4.3 | 169.95 | 33.0753 |
| 12 | V4.3 | 110.15 | 68.2310 |
| 13 | V7 | 21.43 | 32.8913 |
| 14 | V7 | 15.81 | 47.5573 |
| 15 | V7 | 29.38 | 25.5956 |

**解释边界：**同一个函数体在不同提交中也可能因运行环境、编译、测量波动得到不同时间。这里记录的是截图观察，不用点1/2的小幅波动推导某项代码优化必然有效。也没有证据说明15个`T`来自同一份领先提交。

---

## 13. 问题与结论台账：哪些成立，哪些被否定，哪些仍待验证

| 问题 / 当时判断 | 实际证据 | 当前应如何记录 |
|---|---|---|
| 409380与409737计算代码不同导致不稳定 | 旧审计仅发现文件末尾LF差异 | 计算内容相同；根因未唯一定位，不能归咎于换行 |
| 原V4失败一定由SetDim(1)导致 | stable同时改了多项；V4.2审计解释预算与实际核数不同 | 早期过度归因，撤回“已坐实” |
| stable通过就能说明所有多核都不可用 | 后续多组MIX(1,1)与其他版本有完整通过反馈 | stable是隔离手段，不是终局架构 |
| VECIN意味着A2没有C的GM中转 | 后续重评指出接口位置不等于底层通路 | 原V4.3说明需要限定；不能宣称全部逻辑C流量消失 |
| async + 大packet必然快 | V5比V4.3总体退步 | 结构目标不等于实测收益；缺单项消融 |
| V6 READY 0/1冲突是9—12点唯一根因 | V6.1只改编号后相同点仍错 | 编号隔离保留，根因假说未修复观察故障 |
| FIRSTN始终是整个shard平坦M-fast | V6.2分组模型复现1664→2272 | 平坦假设存在真实源码反例，不能普遍使用 |
| V6.2已经证明隐藏9—12点修好 | 没有这四点真实tiling与V6.2评测 | 仅确认模型反例已修；设备结论未知 |
| V6所有分支都延后行归约 | A2_native有，manual_cv/.1/.2没有 | 分文件记录，不混用设计描述 |
| V7所有改善都来自Resident/Skinny | 截图没有shape或分支信息 | 改善已观察，具体分支归因未知 |
| V7.1必然能取得35.08分 | 该数字是两张截图逐点最小值平均 | 只是拼接参照；安全回退还可能改变耗时 |
| CPU模型大量通过等于硬件正确 | 曾共享错误tile假设；fence在模型中可为no-op | 只证明已建模范围，不能替代Bisheng与A2 |
| 合成扩展绝对误差超标可以被忽略 | V7/V7.1审计显式记录 | 保留警告，不能把组合容差换成“精度全过” |

V7.1的`FlatFastStream`不是又一次盲目猜flag，而是把已知顺序风险转为Host可检查的路径接受条件。它并未证明其他全部风险消失，也没有取得新Judge认证。

---

## 14. 验证方式的演进与证据强度

### 14.1 不同“通过”不能混为一谈

| 证据类型 | 能支持什么 | 不能支持什么 |
|---|---|---|
| 源码/字节diff | 实际改了哪些语句、保留了哪些函数 | 编译成功、时序正确、速度提升 |
| Host mock + ASan/UBSan | 普通C++控制流、一次mock launch、分配释放和参数关系 | 真实CANN tiler、Bisheng代码生成、NPU地址/时序 |
| CPU语义适配器 | 模型内数学、覆盖、队列/地址所有权、指定协议 | SDK全部细节、实际Cube累加树、缓存、真实硬件flag |
| 独立负例/错误注入 | 检查器对某类错误具有检测能力 | 对未建模错误没有遗漏 |
| Judge 15/15截图 | 该次评测集合的正确性、显示的15点耗时 | 全合法输入证明、跨版本/跨环境保证 |
| 同机同输入重复profile | 在固定条件下比较路径与流水开销 | 本文没有此类完整新数据，不得虚构 |

### 14.2 主要历史检查记录

下面数字是**读取既有包内报告得到的历史记录，不是本次重新运行**。早期有的报告采用组合容差，具体标准需与该包AUDIT一起看。

| 版本 | 包内主要记录 | 必须保留的限制 |
|---|---|---|
| V4.2 | 23,174组planner；752组合、1,504次CPU语义；768组Host mock | 不是厂商仿真器，无当时新真机结果 |
| V4.3 | 12,699组planner；3,574个Fast plan；112个语义case | 后续发现平坦tile顺序合法域不充分 |
| V5 | 26,464组结构配置；98,304组Bank边界；1,504次CPU语义；1,600组Host | 模拟异步不等于实际取得吞吐重叠 |
| V6 A2_native | 22,464组配置；1,136次CPU语义；12,224个C块协议模型 | 独立测试包；最大绝对差2.44140625e-4，不能称每组abs都小于1e-4 |
| V6 manual_cv | 22,719组配置；1,094次CPU语义；7,244个C块协议；3,200组Host | 旧生产者模型与消费者共享了平坦顺序假设；全量sanitizer尝试曾超时 |
| V6.1 | 两个flag常量的exact diff与静态检查 | 不能宣称新跑过全部设备语义测试 |
| V6.2 | 139,392组游标配置；21,780,000个位置；独立旧错新对反例；1,057次新增分组语义 | 指定Norm模型，不代表用户SDK逐字节实现 |
| V7 | 40,350组面板配置；1,840次CPU语义；2,640组Host | 4个输出独立绝对误差超标；后续另有Judge15/15 |
| V7.1 | 17个模块来源比对；1,536次语义；1,200次Host；147,456组遍历检查 | 12个输出独立绝对误差超标；仍无新Judge |

本档案整理过程中实际新增执行的工作仅为：核对已挂载源码身份与部分差异、读取档案、复算截图分数和生成本Markdown。没有把旧报告里的测试当成本次复跑。

---

## 15. 目前真正沉淀下来的技术资产

### 15.1 可以明确复用的模块及身份

**作为已有有效性能对照：**V4.3保留完整15/15截图；V7也是完整15/15，但收益分布不同。二者构成当前最有用的两份对照，不用V6的WA耗时取代它们。

**作为正在合并的专用模块：**V7 Resident、连续Skinny，以及早已存在的Dot/Tiny。覆盖与路由条件必须和来源函数一同保留，不是把快路径无条件扩大到所有相似形状。

**作为正确性经验：**显式物理跨度；M/N分片先Max再Sum；精确四字节输出；非队列UB的MTE3读生命周期；零有效行AIV仍参与协议；环形槽退出排空；Norm平坦顺序不普适；CPU模型需要独立生成生产者顺序。

**作为待测路线：**A2_native的单M条带本地Matmul、V6.2的整shard本地Matmul、V7显式Panel、V7.1模块混合。它们的状态不同，不能用同一个“V6/V7都验证了”概括。

### 15.2 仍只是候选、不能写成已完成的项目

原方案和后续重评提到过：BasicBlock、MDL、IBShare、L1显式驻留、NZ-native归约、低阶Mmad、更多静态K模板、L2访问提示、离线真机autotune。**截至当前主线源码，不把这些统称为已经落地并取得收益。**

同样，当前没有领先选手源码，没有15点真实shape/dtype/layout映射，没有能把所有瓶颈唯一定位的PMU报告。材料能支持的是“我们做了什么、哪些失败、哪些数据确实改善”，不是反向猜测榜首算法。

### 15.3 后续维护档案的最小记录项

每次新版本补充：明确父版本/移植模块、源码SHA、实际路由条件、数学或同步变化、目标编译结果、独立精度及重复性结果、同输入Task Duration、完整Judge表。新代码没有反馈时继续写“待验证”，不要让版本号自动升级其证据级别。

正式工程仍只替换`code/kernel.asc`；README、测试、profile工具和回退源码作为独立档案保存，不混入评测入口。这个原则沿用已有包的使用方式，不是新增比赛规则。[S05—S14]

---

## 16. 来源目录与文件身份

### 16.1 主要来源编号

| 编号 | 文件 / 压缩包 | 重点依据 |
|---|---|---|
| S00 | `cann(3).md`；当前容器另有题面`cann.md` | 语义、布局、范围、精度、计分规则 |
| S01 | `kernel_v3_1.asc` | `FusedDevice`、`MakePlan`、`GetTiling`、Dot/Tiny |
| S01a | `BMMS_submission_comparison.md` | 409380/409737差异、静默失败、原run.sh覆盖不足 |
| S02a | `BatchMatmulMaxSum_V4_终极冲榜方案.md` | 设计候选集合，不能当全部已实现 |
| S02 | `BatchMatmulMaxSum_V4_kernel.asc`及V4_submission_candidate包 | 原V4二维规划、direct、错位读取、Finish并行 |
| S03 | `BatchMatmulMaxSum_V4_stable_fix_kernel.asc`及同名包`AUDIT.md` | 单组隔离、16行条带、fence |
| S04 | `BatchMatmulMaxSum_V4_1_conservative_kernel.asc`及README | 只扩大baseM，单核不变 |
| S05 | `BatchMatmulMaxSum_V4_2_multicore_kernel.asc`及包内README/AUDIT | 多组MIX(1,1)、persistent shard、SetDim结论更正 |
| S06 | `kernel_v4_3.asc`及`BatchMatmulMaxSum_V4_3_vecin_fast.zip` | Fast/Safe、旧GM流量说法、局部顺序假设 |
| S08 | `BatchMatmulMaxSum_V5_pipeline_kernel.asc`及同名包 | ShortDot、PackedTiny、Bank、Packet异步 |
| S09 | `BatchMatmulMaxSum_V6_A2_native_kernel.asc`及同名包 | 单M条带、双AIV、延后行归约、READY4/5 |
| S10 | `BatchMatmulMaxSum_V6_manual_cv_kernel.asc`及同名包 | 整shard、逐块行归约、READY0/1、旧协议模型 |
| S11 | `BatchMatmulMaxSum_V6_1_flagfix.zip`中的`kernel.asc`、`PATCH.md` | 两个flag常量改动；另附`V6_1_PATCH.md` |
| S12 | `BatchMatmulMaxSum_V6_2_tileorder_fix_kernel.asc`及同名包 | NormTileCursor、旧错新对反例、分组测试 |
| S13 | `BatchMatmulMaxSum_V7_kernel.asc`、`V7_重新评估.md`及reassessment包 | Resident/Skinny/Panel、精度警告、结构代价 |
| S14 | `BatchMatmulMaxSum_V7_1_hybrid_kernel.asc`及hybrid包 | 模块继承、FlatFastStream、fence、当前未测状态 |

原包内的外部文档引用保留在其`SOURCES.md`或`AUDIT.md`。本档案不新增外部研究结论；涉及架构/API的总结采用既有审计的限定条件。

### 16.2 早期源码来源

| 编号 | Library中已定位的文件 | 本文使用的内容 |
|---|---|---|
| E00 | `kernel_submit_v2_0_singlelaunch_correctness.asc` | 初始骨架、MatmulApiTiling |
| E01 | `kernel_submit_v2_0_1_singlelaunch_correctness.asc` | MultiCoreMatmulTiling、SetTail、旧rowBase |
| E02 | `kernel_submit_v2_0_2_singlelaunch_correctness.asc` | 移除SetTail、compact尾块寻址 |
| E03 | `kernel_submit_v2_0_3_singlelaunch_stridefix.asc` | 恢复SetTail并保留curN row stride |
| E04 | `kernel_submit_v2_0_4_singlelaunch_ceilbase.asc` | ceil-base选择 |
| E05 | `kernel_submit_v2_0_5_singlelaunch_tileorder.asc` | 当时观察到的FIRSTN序列、全M rowMax |
| E06 | `kernel_submit_v2_0_6_singlelaunch_batchstride.asc` | 核数限制与batch grid-stride |
| E07 | `batchmatmulmaxsum_submit_clean.asc` | VECIN、Vector行归约、默认MIX(1,2)分支 |

早期文件使用已检索的源码范围与历史对话记录，不为未取得完整提交/评测对应关系的探针编造结果。

### 16.3 截图编号

| 编号 | 对话中的反馈 | 可确认结果 |
|---|---|---|
| I00 | 原V4“然而过不去” | 前两点通过，通用测试大面积失败；末尾画面不完整，不填完整耗时 |
| I01 | V4.3之后，用户要求“严格排除泛化方法，重新设计”时的15点图 | 15/15；点15为110.28μs |
| I02 | V5之后“非常差…重新设计”的15点图 | 15/15；点15为113.71μs |
| I03 | V6 manual_cv之后“分析问题”的图 | 点9—12 WA；点9为88.61μs |
| I04 | V6.1之后“正确性还是不对”的图 | 点9—12 WA；点9为89.77μs |
| I05 | V7之后“能不能和前面的融合”的图 | 15/15；点15为29.38μs |

文件名与对应关系可在本对话附件中追溯；本文表格已自包含全部用于复算的数据，无需额外下载图片才能阅读。

### 16.4 本次实际核对的主线源码 SHA-256

以下哈希由本次对挂载文件字节计算得到；V6.1从其附带ZIP的`kernel.asc`读取。它们用于区别同名路线，不是编译后二进制哈希，也不是Judge后台提交标识。

**V3.1** — `kernel_v3_1.asc`，574行，26160字节。

```text
d53fb4cf4adb72fa0ed2e7af9fa48aeb357e771563f64ba118f8bd7b61643a99
```

**V4** — `BatchMatmulMaxSum_V4_kernel.asc`，763行，33119字节。

```text
0dbe261e228c460d14a1af20c66a4453c1e904977e22698121ec51bda76f8e4c
```

**V4 stable-fix** — `BatchMatmulMaxSum_V4_stable_fix_kernel.asc`，588行，26733字节。

```text
7c12c18e65089a18cdcb2a16e59bb6c5f5a8bbcc1a521f61de6955e21b9df030
```

**V4.1** — `BatchMatmulMaxSum_V4_1_conservative_kernel.asc`，590行，26909字节。

```text
3daface7517e2c1ed15f6bbba738e22578cb608ced292587e2c12313e42e690a
```

**V4.2** — `BatchMatmulMaxSum_V4_2_multicore_kernel.asc`，669行，30624字节。

```text
e0981915047dbef6139197617a19c0ebee594c7b45b8a039b5abb68bbff2264d
```

**V4.3** — `kernel_v4_3.asc`，1145行，51251字节。

```text
893b84302d71c5da76bc7e6f6bd1af944a3ee6c16f3ad3ae90da73da7a0dec51
```

**V5** — `BatchMatmulMaxSum_V5_pipeline_kernel.asc`，946行，45456字节。

```text
c1a00920d69ae5807a2bf607e0f94b5377b7026bdcdebdc4fdd423357ef52f5e
```

**V6 A2_native** — `BatchMatmulMaxSum_V6_A2_native_kernel.asc`，602行，29412字节。

```text
68e941171aa1cd015bd8726decc2b1cdceb151123f26a708113a5968b62a2df8
```

**V6 manual_cv** — `BatchMatmulMaxSum_V6_manual_cv_kernel.asc`，603行，29492字节。

```text
bdfc54e03332954f4430d0fe8cbb5c3859bfc2a09d6fda35dfbc035eae65e4ca
```

**V6.1** — `BatchMatmulMaxSum_V6_1_flagfix.zip :: kernel.asc`，606行，29710字节。

```text
6bba3ea83bcafe8ccea85630ef996674808ea5f2ffd9eea387face94b6382823
```

**V6.2** — `BatchMatmulMaxSum_V6_2_tileorder_fix_kernel.asc`，649行，31514字节。

```text
fcb325ca5b152c17b56745d95bb0d1f176fa6770bd30422db5a57c8ee8d2f98b
```

**V7** — `BatchMatmulMaxSum_V7_kernel.asc`，651行，36075字节。

```text
a3262ffbcc0366590f254415e1d6b8da12772ab032a323f7475048fbdfdb1328
```

**V7.1** — `BatchMatmulMaxSum_V7_1_hybrid_kernel.asc`，1450行，68307字节。

```text
d7f21ab436e8eaf5d30245c18fc97465754832236bdb8478ae320cc94056d97c
```

V3.1旧审计另记录26161字节、带末尾LF的409380版本哈希为：

```text
a9252c5db461f4f9b780524f4bf05493017d27c6af9e721d59ea8125a4ecdd61
```

当前容器副本为26160字节，对应409737的末尾无LF变体。旧审计确认差异仅在文件结束。[S01a]

---

## 17. 归档结论

**已有最清楚的实测事实是：V4.3的通用计算整体表现较好，V7在部分输入上的新路线带来显著改善，但V7通用面板也引入明显退化；V7.1正在按模块组合两者，而不是已经实现逐点最优。**

这段迭代沉淀的不只是kernel版本，还包括四条不能再混淆的边界：**接口名不等于硬件数据通路，源码结构变化不等于提速，CPU模型通过不等于真实时序正确，某次15/15不等于所有输入和所有后续组合都已经正确。**

后续继续推进时，以本档案中的具体文件与证据状态为起点，不再用笼统的“旧V6”“最新版本肯定更好”替代可追溯记录。

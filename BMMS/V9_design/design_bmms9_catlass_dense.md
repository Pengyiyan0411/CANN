# bmms9_catlass_dense 详细设计

状态：设计规格，未生成可提交内核。下述单 FP32 C 的 D0 作为吞吐/集成诊断主体；已知强消减反例意味着它不能单独成为严格数值提交候选，需组合 [数值路线](precision_route.md) 并整体验收。主路线与决策背景见 [V9 冲榜路线设计](../BatchMatmulMaxSum_V9_冲榜路线设计.md)。内部模块名含 catlass；官方算子名和 ABI 保持原样。

## 1. 接口与数学契约

沿用 P01：

```cpp
extern "C" void run_kernel(
    GM_ADDR a, const TensorGroupInfo& ia,
    GM_ADDR b, const TensorGroupInfo& ib,
    GM_ADDR y, const TensorGroupInfo& iy,
    int64_t availableCoreNum, aclrtStream stream, bool ta, bool tb);
```

输入 FP16/BF16 同类型；输出 FP32[B]。逻辑 shape 为 A[B,M,K]、B[B,K,N]，只按属性解释物理存储。约束：B1..64，M/N1..8192，K32..8192 且 K%8=0，BMK/BNK≤2^26。连续 ND，输入不可改，多次结果一致。计算 `sum_m(max_n(dot_k(A,B)))`；完整 FP64 golden 最后一次转 FP32。现有 PyTorch bmm/amax/sum 组合描述数学语义，不另造同名框架 API。

| ta/tb | A 物理形状 | B 物理形状 | 每 batch 元素偏移 |
|---|---|---|---|
| false/false | M,K | K,N | A=mK+k；B=kN+n |
| false/true | M,K | N,K | A=mK+k；B=nK+k |
| true/false | K,M | K,N | A=kM+m；B=kN+n |
| true/true | K,M | N,K | A=kM+m；B=nK+k |

地址用足够宽的整数计算；batch base 分别为 bMK、bKN。不得从 M=N 或 stride 猜转置。

## 2. 组件选择与工程边界

官方 CATLASS v1.4.0 commit `bcb3e52b6be3004b28996fb48af65ce48710c8f4` 保存在 `references/catlass`。此版本是否能直接用赛方 CANN9 编译仍待编译确认；选择固定版本是为了可复查。

| 层 | 初版选型 | 约束 |
|---|---|---|
| Arch | `Catlass::Arch::AtlasA2` | dav-2201 目标，核数取调用契约，不固定为 20 |
| BlockMmad | `MmadAtlasA2Pingpong` 对应 `Gemm::Block::BlockMmad` | 全 K；L1/L0 M/N 相同；L0C 单缓冲 |
| L1 tile | 初始 64×128×256 | A/B 各 2 stage |
| L0 tile | 初始 64×128×64 | A/B 各 2 stage，C 1 stage |
| A/B 类型 | half 或 bfloat16；按 ta/tb 选择 Row/ColumnMajor | Cube 输入不先升成 FP32；累加 FP32 |
| C 类型 | FP32 RowMajor，显式 ring stride | 不降回 FP16/BF16 |
| Kernel | 自定义 `Bmms9DenseKernel`（拟新增） | 不直接使用完整 C workspace 的 MatmulEpilogue |
| Scheduler | 自定义静态 B/M shard，必要时 N shard | Producer/Consumer 从同一 Plan 推导完全相同顺序 |
| Tile epilogue | 拟新增 `TileBmmsRowMax` | 非逐元素 epilogue，不能套 ElemWiseNoSource 的假接口 |
| Block epilogue | 拟新增 `BlockBmmsOnlineMax` | 持有跨 N 的每行状态；最终全局合并 |

首轮不混用 `ASCENDC_CUBE_ONLY` 全局宏与原 SDK MIX fallback。若提交环境不含 CATLASS，交付必须收敛依赖到单个 `kernel.asc`，保留来源、版权及许可证要求；或依据其流水机制实现只依赖赛方 CANN 的最小 AscendC 版本。不能要求评测安装仓库、改 CMake、使用新 DSL 或提交多个新增头文件。详细依赖/许可审查见 [catlass_feasibility.md](catlass_feasibility.md)。

## 3. 分核、分块与输入重读

第一版固定 nShard=1；`mTiles=ceil(M/TM)`，`pM=min(mTiles,max(1,ceil(cores/B)))`，任务数 `B*pM`，`blocks=min(cores,tasks)`。每个静态任务的 M tile 范围为 `[s*mTiles/pM,(s+1)*mTiles/pM)` 向下取整。组 g 依次处理 `g,g+blocks,…`，不得假定 task 数≤物理组数。

仅空间并行不足且不适合 S 路线时，后续测试有限的 pN 候选。N 分片同样基于 tile 索引向下取整，范围不得为空。候选比较须使用每个实际 shard 的最小/最大工作量，不能再用 `ceil(total/splits)` 冒充最小工作量。pN>1 必须保留逐行 partial max。

Producer 循环顺序是 task → M tile → N tile → K stages。一个 TM×TN 的 C 在 L0C 内从第一个 K stage 累加到最后一个，之后才写 GM。下一输出 tile 通常重新读取输入 K 段；初版不声称跨全部 N 驻留 A。

对完整对齐形状、此循环顺序的逻辑输入读取量近似 `2*B*K*(M*ceil(N/TN)+N*ceil(M/TM))` 字节；真实 cache/HBM 流量可能更小，不能据此直接预测时间。C 写+读逻辑量约 `8*B*M*N` 字节，padding 可能增加。ring 控制峰值空间而非这个总量。

## 4. 资源预算

容量参照固定源码 `include/catlass/arch/arch.hpp`：L1 512 KiB，L0A/B 各64 KiB，L0C128 KiB，UB192 KiB；编译/运行阶段仍核对实际目标资源。官方说明：[Atlas A2 硬件基础信息](https://catlass.readthedocs.io/zh-cn/latest/2_Design/01_kernel_design/00_basics/atlasA2_hardware_info/)。

默认 TM64/TN128/K1=256/K0=64，FP16/BF16 预算相同：

| 存储 | 缓冲/公式 | 字节 |
|---|---|---:|
| L1 | A：2×64×256×2 | 65,536 |
| L1 | B：2×128×256×2 | 131,072 |
| L0A | 活跃 tile：2×64×64×2 | 16,384 |
| L0B | 活跃 tile：2×128×64×2 | 32,768 |
| L0C | 1×64×128×4 | 32,768 |
| UB / 每 AIV | C 输入双缓冲：2×32×128×4 | 32,768 |
| UB / 每 AIV | 可破坏的归约 scratch：32×128×4 | 16,384 |
| UB / 每 AIV | row-max/current 两组：2×64×4 | 512 |
| UB / 每 AIV | merged/tmp/sum 三组上界：3×8192×4 | 98,304 |
| UB / 每 AIV | API scratch 预留及标量输出 | 8,224 |
| **UB 总和** | 保守不复用不同阶段 buffer | **156,192** |

CATLASS Resource 可按整块硬件存储预分配，表中的 L0A/B/C 是有效 tile footprint，不意味着剩余部分能被另一个 allocator 再次分配。事件 ID、TPipe 与 CATLASS Resource 只设一个明确所有者；不能让两个管理器重叠管理同一物理区。8 KiB API scratch 是设计预留，不是已确认的所有 API 需求，代码阶段按所用归约 API 校验。

相同保守 UB 布局下，128×128、64×256 等更大 C tile 会因仍保留三组全 M 合并数组而超预算，已被离线检查拒绝。后续可在所有 C 消费和队列排空后复用同一 UB arena，把生产阶段与最终合并阶段预算取 max 而非求和；这是第二阶段设计，不默认其生命周期已被证明。

GM ring：`align(4*blocks*R*G*TM*TN,512)`，初版 R=2、G=1。默认每组64 KiB。partial：`4*B*pN*Mpad`，Mpad=ceil(M/8)*8，行 padding 不参与最终 Sum。总 workspace 为两段对齐相加，并按最终选用的同步 API 另计其必需 GM 同步区（若该 API 不使用 GM 同步区则为0）；纯低阶 D 不无故附加 SDK 的固定 system workspace。原 fallback 仍用原分配逻辑。

最终 Sum 暂保留完整逐行 max，不先对 M tile 求 scalar sum，以免同时改变数值归约路径。pN1 也保留该格式作为首轮稳定对照，后续才对比省略全局会合的单组直写分支。

## 5. 生产消费时序与伪代码

以下是 API 级设计纲要，不是可编译实现。CrossCore flag 的具体编码与当前 CANN 的两 AIV 收齐语义必须使用现有可靠模式并上机核验；不把 Python 状态模型称为硬件证明。

```text
Host:
  验证 ABI / shape / dtype，选择已验证的公开条件分支
  构造 Plan，分配 ring + partial，只启动一次 __mix__(1,2) kernel
  按现有资源生命周期保证 kernel 使用结束再释放 workspace

AIC producer（每组）:
  两槽第一次使用直接跳过 FREE 等待，不预发虚假信用；遍历同一个 Plan
  for 每个 M tile, 每个 N tile:
    若 seq>=2，等待 ring[seq % 2] 的两个 AIV 都完成上次读取
    for k0 in [0,K), 分成 K1/K0:
      CopyGmToL1 / Nd2Nz + event wait/set（带真实边界）
      LoadData L1->L0A/B
      Mmad(FP32 L0C, first_k ? 初始化 : 累加)
    Fixpipe FP32 -> ring[slot]，固定 stride TN
    在 FIX 完成后发布 READY(seq)
    seq++
  退出前仅排空实际已发布任务的未完成写、信用和局部事件，不等待未发布槽

AIV consumer 0/1（每组）:
  for 同序列 M tile:
    Duplicate(rowMax, -INF)
    for 同序列 N tile:
      等待 READY；按各自真实行范围 DataCopyPad 到 UB
      MTE2 完成后发布本消费者 FREE；零有效行也完成协议
      将无效 N lane 设为 -INF
      拷贝到独立 scratch，WholeReduceMax / ReduceMax 得到每行值
      Max(rowMax, rowMax, currentRows)
    DataCopyPad -> partial[batch,pN,m]，仅写真实行
  所有 MTE3 写完成后，全部参与 AIV 到达合法统一 SyncAll
  指定输出 AIV 按 ns 顺序 Max 合并每行 partial
  对真实 M 行执行固定归约顺序的 ReduceSum，DataCopyPad 写 FP32 y
```

FREE 在拷到 UB 后即可发出，不用等 Max；但 UB 输入槽自身直到 Vector 使用结束才可重用。READY 不能仅凭 C++ 函数已返回发布。AIC 必须等两个消费者，不可收到任一 FREE 就覆盖。尾 M 奇数时消费者的行分工用真实边界（例如按64行 tile 的32/32区间分别截断），不能沿用 `mr/2` 丢掉最后一行。

全局 barrier 的参与者、调用次数必须相同；没有任务的已启动 AIV 也必须按协议参与。不得让 AIC 等待一个被全局 barrier 阻塞的 AIV 所持 ring 信用。最终 barrier 放在所有局部生产消费完成之后，代码需画出 wait-for 图复核。部分矩阵 copy 不得越界借用相邻 batch；K padding 清零，N padding 为负无穷，M padding不参与输出。

## 6. 自定义归约组件契约

| 项目 | 设计 |
|---|---|
| Tile 名称 | `TileBmmsRowMax`，拟新增 |
| 输入 | FP32 UB C 子块，真实行数、真实 N 长度、显式 stride |
| 数学行为 | 每行对本 N tile 取 Max，更新对应持久 rowMax |
| 额外 GM 源 | 无；但有持久 UB 状态，不等同于无状态逐元素 NoSource |
| computeLength | 默认32×128=4096 FP32元素/消费者/块；越界 lane屏蔽 |
| Block 组装 | GM→UB Copy → 局部 row max → 跨 N Max → partial CopyOut |
| 最终合并 | Max(partial_N) 按行完成后 Sum(M)；不把每 N shard 先 Sum |
| 初值 | 负无穷，仅有效行列参与输出；不由有限输入推断 FP32 结果必定有限 |

默认独立 scratch 避免 Reduce 操作破坏仍要使用的数据。较高效的“多个 N tile 先按 lane Max、最后一次行归约”可以作为后续单变量对照；只有同一行的 lane 对应关系及 N tail处理明确时才使用。

## 7. Plan 字段与版本分派

Plan 至少包括：`B,M,N,K,dtype,ta,tb,routeId,TM,TN,K1,K0,pM,pN,tasks,blocks,Mpad,ringSlots,tilesPerPublish,ringBytes,partialOffset,workspaceBytes`。地址计算字段用64位；模板实例由 dtype×布局×tile ID 决定，不把 K32..8192 每个值全部模板展开。

初版只实现默认64×128及必要的小输出专用版本；32×64/K1=128/K0=32 与64×128/K1=512/K0=64已通过当前算术预算，但留作有瓶颈证据后的对照。单个构建不同时排列组合大量模板，以控制编译成本。

G=2 的批量发布可减少交接次数，但增加等待首包和 GM ring 空间；同一包尾部不足2块时必须明确有效块数。它不减少总计算/搬运，也不能用它掩盖 AIV实际更慢。首次实现保持 G=1。

## 8. 正确性、数值和验收

语义：完整 K → Max(N) → Sum(M)，四种物理布局，负值、尾块、B配对、输入只读、确定性。数值：完整 FP64 golden，最终转 FP32；FP32 C 并无全域严格误差保证，反例及处理原则见主路线文档。没有实际精度通过报告前，所有新分支均不应成为正式提交默认。

验证层次：Plan/地址/资源离线 → 编译 → 32 smoke + 数值反例 → 代表 shape 精度 → 性能初筛 → 四布局双 dtype及边界全集 → 候选提交。每个实际 device 输出附源码 SHA、分流参数、精度指标及重复一致性。CPU Shim 不能验证 Nd2Nz、Fixpipe、event 或实际设备时序。

D 进入下一轮的条件：同形状新融合路径相对 P01 有超过测量波动的收益，未出现精度/内存/死锁问题，且 GEMM-only/完整融合对照能解释差距。若只看到 standalone GEMM 更快而融合总时间不快，先修消费者/交接；若 GEMM 主体更慢，先选 tile/输入复用或否定此组件，不继续调 pM/pN 掩盖它。

# V9 S：小输出、长 K、NT 的确定性 Vector / Split-K 候选

状态：实现片段，尚未经过本地 CANN 编译或 NPU 测试。此文件不是性能达标声明。

`splitk_fragment.asc` 放在完整 P01 已有模块之后、原公开 `run_kernel` 之前。在原入口完成所有公开接口检查后、旧 Tree/Native 分流前调用：

```cpp
if (bmms9s::TryLaunch(a,ia,b,ib,y,iy,availableCoreNum,stream,ta,tb)) return;
```

只对 `TA=false, TB=true`（A 物理 `[B,M,K]`、B 物理 `[B,N,K]`）接管。FP16 与 BF16 均先 Cast 到 FP32。NN/TN/TT 全部返回 false、保留 P01。输入域为：

- `2 <= M <= 32`, `2 <= N <= 64`, `1024 <= K <= 8192`, `K % 8 == 0`。
- `M*N <= BMMS9S_MAX_MN`；默认宏值 256，硬上限 2048。后续若明确实验可改宏 2048。
- `B * ceil(M/16) * ceil(N/16) < availableCoreNum`，只探索 Cube 空间并行不足的输入族。
- 保留原题面 B、dtype、输入尺寸等完整约束，由原入口先检查。

## 固定任务与存储布局

`S = min(ceil(2*cores/(B*M*N)), floor(K/1024))`，下限 1。

每任务处理 `(b,m,n,s)` 的一段点积，任务编号 `(((b*M+m)*N+n)*S+s)`。K 以 8 项为量子均匀切分：`kBegin=floor(s*(K/8)/S)*8`，`kEnd=floor((s+1)*(K/8)/S)*8`。所有分段覆盖完整 K 且无重叠、无空段。`S=1` 时是小输出 Vector 点积路径；只在独立点积数不足以占用全部可用 AIV 时启用跨核 Split-K。

每任务独占一个 32 字节 workspace 记录：`[hi,lo,0,0,0,0,0,0]`。总 workspace 是 `B*M*N*S*32` 字节。任务循环由 `worker, worker+workers, ...` 分配，写入地址互不重叠。一个 `__mix__(0,1)` launch 使用 `min(2*cores,tasks)` workers；全部 partial 发布后执行一次全 AIV barrier，然后每个 batch 由一个 worker 完成最终合并。没有 AtomicAdd，没有第二次 kernel launch。

## 计算顺序与精度边界

每个 K shard 再切成 256 项块。两个连续向量只读取有效项；输入 UB 先清零，尾项为 0。FP32 乘积采用已有 P01 `PairAccumulate` 做固定二叉 hi/lo 归约，折半到 8 项；随后按 lane 顺序用规范化 scalar TwoSum 合并。跨块、跨 K shard 均按固定顺序合并。

每个完整 C 元素保留规范化 `(hi,lo)`，在全部 K 完成后按 `hi`、再 `lo` 字典序做 N 维 Max；保留胜者的两个分量再做 M 维补偿 Sum，最后才转为单个 FP32 输出。不能先对分段 C 做 Max；不能在完整 C 与 Max 之间丢弃低分量。

这一结构旨在避免“先将 C 舍入 FP32，再做强消减 Sum”丢低位，例如 `4096+2^-13` 与 `-4096` 的两行结果。但双分量算法仍不等于全域 FP64：低分量自身舍入、非正规数、溢出、编译器重结合以及设备具体浮点行为仍需实测。请勿使用允许重结合的 fast-math 选项；题面若未限制输入量级，不能只凭普通随机输入宣布全合法域数值保证。

独立精度审查已找到域内反例，故本版本仅为实验候选，不能称全域精度通过：`B=1,M=32,N=2,K=1024`，每行 A 前五项为 `[32768,8,2^-9,-32768,-8]`，两行物理 B 的前五项均为 `[32768,8,2^-9,32768,8]`，其余为 0。每个精确点积为 `2^-18`，golden 为 `2^-13 = 0.0001220703125`；当前双分量模型输出 0，FP16/BF16 都超过绝对误差门槛。另有 BF16 `2^64 * ±2^64` 先溢出、随后精确抵消为有限数的反例。详细可复现测试由 `test_semantics.py` 与 `precision_review.md` 保存；平台普通用例通过也不能覆盖这些边界。

## UB 与同步审查

| 缓冲 | 字节 |
|---|---:|
| 两个 256 项 FP16/BF16 输入，单队列 | 1024 |
| FP32 product 与第二输入 | 2048 |
| FP32 low | 1024 |
| 三个 128 项 TwoSum scratch | 1536 |
| 输出 / partial 记录队列 | 32 |
| 单 batch 全部 partial 读取 | `M*N*S*32` |
| 合计 | `5664 + M*N*S*32` |

默认 MN<=256 且 cores<=64、S<=8 时，`MN*S<=256`，总 UB <= 13856 字节。扩域 MN<=2048 时，UB <= 71200 字节。均不依赖 8192 长 K 全量驻留；固定 tile 长度是算法参数，不是运行时核数假设。

同步沿用 P01 已使用的 `Fence`、`TQue`、`SyncAll<true>` API：

1. Vector 清零输入后 V→MTE2 fence，DMA 后输入队列交给 Vector。
2. hi/lo 树之后 V→S fence，Scalar 读取后 S→V fence，避免复用冲突。
3. `oq.AllocTensor` 后先 V→S 接通队列复用的 MTE3→V 依赖，Scalar 才可写 UB；Scalar 写完后 S→V 接通队列的 V→MTE3 依赖。partial 和最终输出两处均应用。
4. partial 写出完毕经 MTE3→MTE2 fence 和全 AIV barrier；最终 DMA 经 MTE2→S fence后读取。
5. 每任务 32B partial记录不共享写区；最终 y 按 batch 写精确 4B，采用与 P01 相同的 DataCopyPad 方式。

## 待验证事项

本地已执行 199,496 组接管规划检查（8 种核数、8 种 B、M/N 全域及 11 个 K 边界）：K 分段无空隙/重叠/空段、task/workspace 编号与 UB 界限全部通过；所枚举集合最大 UB 13,856 字节、workspace 253,952 字节。这是规划检查，不能替代设备运行。

- CPU 模型应覆盖 8 项 K 量子的非 256 尾、S=1 与 S>1、全负、强消减、近 Max 平局、FP16/BF16、B>1 以及核数变化。
- CPU 只能核对规划、地址和所建模的运算顺序，不能验证 CANN 模板编译、异步指令顺序、真实硬件屏障和性能。
- 首轮平台提交单独开启本分支、保持其余 P01 不变。即使通过，也必须用完整 15 点表复算，而不能假定 Case 15 属于本分支。
- 本分支以更多重复输入搬运换取更多 Vector 独立任务；Scalar 最终合并也有开销。不能承诺所有接管输入比 Cube 更快。默认 256 上限限制首次实验风险。

已读已有 AscendC 设计/归约/流水技能资料，并复用 P01 的已存在 API。当前环境未提供 `ascendc-operator-code-gen/references/`；未伪称加载该缺失目录，亦未引入其中未核对的接口。

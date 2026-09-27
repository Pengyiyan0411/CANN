# R25：仅对已定位的 Native K128 两类输入特化

2026-09-27。父版为冻结 R23_SPLIT_K。当前用户要求：直接优化 Case5/13/14，验证完整 15 点后，
再推进其他点。本轮不生成新探针，不改变 Case7/15 的既有路线。R25 是待测候选，R23 仍是已验证基线。

## N01–N05 结论及分派

| 对象 | 本批强阳性 | K | M/N | B |
|---|---|---|---|---|
| Case5 | N03=14.67、N04=14.60 μs | 128 | 各为 16 或 32 | 2–64 |
| Case13 | N05=98.42 μs | 128 | 均≥48、16 对齐 | 1 |
| Case14 | N05=43.23 μs | 128 | 均≥48、16 对齐 | 1 |

三点的 N01/N02 都无大幅响应。本批其他条件命中时执行的是完全相同的压力计划，
所以已提供各点的阳性校准，双阴性可以在 Native 固定 K 集合中排出 K128，无须再补 C00。
Case5 两个方向都小，仍属于源码的 Dense_SmallK；不能误归为 ShortM/ShortN。
详细原图和 75 行测量见 `V11_results/2026-09-27_d24_native`。

新选择器只在 R23 原 Native 分支已经选中并生成原 MakeNative 计划之后执行：

```cpp
small = K==128 && B>1 && M<=32 && N<=32 && p.blocks>1;
dense = K==128 && B==1 && M>32 && N>32 && p.blocks>1;
```

原 Native 门槛继续负责 M/N≥16、16 对齐和排除 Tiny/Resident。两条件互斥。
`blocks>1` 限制到具备可破坏并行度的输入，单核组计划沿用原内核；这与本轮强压力证据相符。
选择依据真实元数据，不用测试点号、输入数值、跨调用状态或未证实的精确 shape。
MakeNative、tasks、blocks、pM/pN、workspace 字节数、Cube 生产者、所有旧设备函数均未修改。
未命中新条件时，继续发射原来的同名内核；更早的 Macro/Split-K/R03 和最后 fallback 都不改。

## Case5：完整 batch 在一个 AIV 上直接完成

这里 `mTiles=nTiles=pM=pN=1`，每个 batch 的完整 C 已由一个核组算出。
原消费者把行均分给两个 AIV，再写 partial、全局同步、读回完整 M 求和。
新消费者按核组本地 seq 的奇偶，把完整 batch 交替分配给两个 AIV：

1. 两个 AIV 仍在每包开头等待 READY，包尾或最后残包都发送 FREE。
2. 拥有该 batch 的 AIV 用二维 DataCopyPad 只读 M×N 有效值，UB 行距=N。
3. WholeReduceMax 的 mask=N、repeat=M、源行距=N/8，直接得到全部 M 行的最大值。
4. 沿用 FP32 ReduceSum，按原 M 顺序求和，直接写一个输出。

另一个 AIV 即使该包没有自己负责的 tile，也必须归还信用。模式 2 的 AIC 等待两个 AIV
都发送信号，这是保留双参与者的依据。[官方 CrossCoreSetFlag](https://www.hiascend.com/doc_center/source/zh/canncommercial/80RC3/apiref/ascendcopapi/atlasascendc_api_07_0260.html)

不再写/读 partial、不调用 SyncAll、不初始化 128 列的 -inf UB、不执行多余 128→64 折叠。
M/N 均 16 对齐且≤32，所以整行 DMA 覆盖所有将参与计算的元素，无须尾列填充。
GM packet 的四 tile 布局和生产者两槽信用协议保持不变；未减少 Cube/Fixpipe 的数学工作。
UB 最大为 `32*32*4 + 2*32*4 + 32 = 4384 B`，单 batch 对应一个输出写者。

[WholeReduceMax 文档](https://www.hiascend.com/doc_center/source/en/CANNCommunityEdition/850/API/ascendcopapi/atlasascendc_api_07_0079.html)
支持 A2 float 的 ORDER_ONLY_VALUE；此处 mask=16/32、repeat=16/32，源/目的对齐满足其要求。

## Case13/14：一次收集 N 分片，在 UB 中合并

原 B1 尾段在 worker0 上循环 pN 次：每次单独 DataCopy，再做 Max，并在搬运和 Vector 之间切换。
新 `DenseGatherConsumer` 保持第一阶段消费、partial 布局和一次 SyncAll 不变，只替换末段：

```cpp
stripeRows = min(M, floor(16384 / pN / 16) * 16);
for (row stripe) {
    DataCopyPad(values, partial[row0], {pN, rows*4, (M-rows)*4, 0, 0});
    Fence<MTE2_V>();
    // [pN][rows] -> [rows], no padded shards.
    while (active > 1) {
        pairs = active/2; keep = active-pairs;
        Max(values, values, values[keep*rows], pairs*rows);
        PipeBarrier<PIPE_V>(); active = keep;
    }
    Max(merged[row0], values, values, rows); // exact value copy, no added sum
    Fence<V_MTE2>();
}
ReduceSum(y, merged, scratch, M);
```

最后 M 向量完整保留，求和长度、顺序和输入 dtype 不变。pN1 时仍是原来的一次全 M 读取。
奇数 active 保留中间那份，再与高半部分合并；不能用简单 active/2 丢弃奇数分片。
树只重排 Max，普通有限点积结果保持最大值；已有极端 BF16 溢出/NaN 和 FP32 消去限制未被证明消除。

这不同于旧 R12：没有新增全局屏障、没有并行 scratch 写回；也没有重做旧 R05 的第一阶段延迟 Max。
收益假说集中在末段 DMA 发射和往返依赖，若真实 pN=1 或尾段非瓶颈，Case13/14 可能无明显收益。
现有结果不足以证明其真实 pN，不能把这一假说写成已定位的硬件瓶颈。

DataCopyPad 的 GM 源间隔以字节计、UB 目的间隔以 32B 计。这里两者分别是 `(M-rows)*4` 与 0，
每行大小为 64B 的倍数；blockCount≤64，单块≤32768B。
[官方 DataCopyPad](https://www.hiascend.com/document/detail/zh/canncommercial/800/apiref/ascendcopapi/atlasascendc_api_07_0265.html)

| AIV 分配 | 最大字节数 |
|---|---:|
| 第一阶段 cq + groupBuf | 32768 |
| oq + rowBuf + runningBuf | 1184 |
| mergedBuf + sumBuf | 65536 |
| packed N 分片 tmpBuf | 65536 |
| 合计 | 165024 |

显式 UB 分配低于模型的 192KiB 限制；编译器额外资源仍待 CANN 编译确认。
Cube 侧继续 L1=327680、L0A=32768、L0B=65536、L0C=65536 B。
GM ring 与 partial 申请量保持 R23，即小矩阵虽不再使用 partial，本轮也不更改 workspace 契约。

## 验证证据与边界

- 原版和候选各执行 222 次源码模型、70 次隔离尾段检查，共 146 对重复检查。两版普通输出逐位相同；
  对 FP64 参考最大绝对差约 4.77e-7。覆盖 FP16/BF16、四种转置、全负值、零、普通非二进制分数、
  M/N 尾块、完整/不足四块包、多次回绕、多 batch、正反线程启动和条件外 Native。
- 18,828 次真实 host 分派执行：18,444 次未命中条件的全部记录等于 R23，核数、计划、内核绑定、
  workspace 和分配生命周期均一致。覆盖六条旧路和 16 个新 dtype/layout 绑定。
- 32,640 组容量/跨度检查，64 种 pN 树覆盖，92,481 个小矩阵 packet 分配检查。
  packed DMA 调用数在域内不超过原 pN 次，显式 UB 上界 165024 B。
- 三个错误注入被拒绝：让 AIV0 错拿全部 tile、奇数 N 树丢分片、去掉 B 条件扩大分派。

例子均为合成输入，不是隐藏 shape：B3/M32/N32/K128/20 核组从一次全局屏障降为零，
partial 读写各 96 个 float 降为零；B1/M256/N1024/K128/20 核组末段 DMA 4→1，
分核、矩阵乘次数、C/partial 字节数和一轮全局同步不变。它们是逻辑工作量，不是 NPU 时延。

本地无 CANN/NPU，不声称完成目标编译或证明所有非目标点时延不退化。
新源码虽然严格限制输入域，未知测试点的完整元数据仍不可见；最终必须以完整 15 点和相邻 R23 对照验收。
在 R25 平台结果到来前，不升级 SOTA、不继续推进其他点。

# BatchMatmulMaxSum V8 精简冲榜方案

## 1. 核心目标

本题不是单纯把 BMM 做快，而是尽量避免完整相似度矩阵 `C[B,M,N]` 落到 GM。

目标数据流：

```text
X1/X2
  ↓
Cube GEMM tile
  ↓
Vector ReduceMax(N tile)
  ↓
跨 N tile 更新 rowMax[M tile]
  ↓
ReduceSum(M)
  ↓
y[B] / 极小 partialY
```

核心收益：

- 不写完整 `B×M×N` FP32 中间矩阵
- 不再单独启动 ReduceMax / ReduceSum 大 kernel
- Cube 计算后直接接 Vector 归约
- 只保留很小的 `rowMax[M_tile]` 或 `partialY`

优先级：

```text
Streaming Fusion  >  Split-M  >  selective Split-N  >>  Split-K
```

Split-K 暂时不做：Max 必须等完整 K 点积结束，Split-K 会引入 partial-C 合并，破坏融合收益。

---

## 2. 只做 3 个版本

### V8.0：先把最大收益拿到 —— Streaming Fusion

这是必须先做的版本，也是最可能直接产生大幅提升的版本。

每个 work item 负责：

```text
一个 batch b + 一个 M tile
```

核心循环：

```cpp
for each M_tile:
    rowMax[Mt] = -INF

    for each N_tile:
        C_tile = X1[M_tile, :] @ X2[:, N_tile]   // Cube, FP32 accumulate

        // 不写完整 C 到 GM
        C_tile -> Vector

        // N tail 无效位置必须设为 -INF
        tileMax = ReduceMax(C_tile, dim=N)
        rowMax = Maximum(rowMax, tileMax)

    partialY = ReduceSum(rowMax over valid M rows)
```

先只做最稳的并行策略：

```text
B 足够大：按 B 分核
B 小、M 足够大：按 (B, M_tile) 分核
```

如果一个 batch 被多个 M tile / core 拆开，每个 core 只输出一个 FP32 `partialY`，最后做一个极小的 final reduction。

### V8.0 必须同时保证

1. FP16 / BF16 输入，K 维 FP32 累加。
2. NN / NT / TN / TT 四种 storage layout 正确。
3. N tail 的 padding 不能是 0，必须按 `-INF` 处理。
4. M tail 只能 Sum 有效行。
5. `rowMax` 初值必须是 `-INF`，不能是 0。
6. 不额外做 transpose kernel。

### V8.0 初始 Tiling

不要一开始全空间 autotune，只试少量候选：

```text
(Mt, Nt) =
(64, 128)
(64, 256)
(128, 128)

Kt = 64 / 128
```

优先从：

```text
Mt = 64
Nt = 128 或 256
```

开始。

选择原则：

```text
能放下 FP32 C tile + rowMax + 必要 buffer
同时尽量让 Nt 大，减少 N-loop 次数和 X1 重复搬运
```

---

### V8.1：只补最大的短板 —— Split-N

V8.0 如果碰到：

```text
B 很小
M 很小
N 很大
```

例如：

```text
B=1, M=16, N=8192
```

按 M 分核会严重吃不满核心。

这时只增加一个特殊路径：Split-N。

```text
Core0 → N shard 0 → partialMax[M]
Core1 → N shard 1 → partialMax[M]
Core2 → N shard 2 → partialMax[M]
...
```

最后：

```text
rowMax[m] = max(partialMax[:, m])
y = sum(rowMax)
```

它产生的中间量只是：

```text
numCore × M × FP32
```

远小于完整 `M×N` 相似度矩阵。

### V8.1 Dispatcher

只保留三类，不搞五六类复杂 regime：

```cpp
if (B * ceil(M / Mt) >= enough_work_items) {
    // 主路径：B / M 并行
    RunSplitMOrBatch();
}
else if (N is large) {
    // 小 B、小 M、大 N
    RunSplitN();
}
else {
    // 小 shape 继续用主路径，先不做独立 microkernel
    RunMainKernel();
}
```

先不要做 Split-K、独立 Tiny Kernel、K-heavy 专门 kernel。

---

### V8.2：只做一次定向性能冲刺

前两版正确后，不再增加新架构，只根据 profiler 做一次定向优化。

优先顺序：

#### 情况 A：Cube 等数据 / MTE2 占比高

做：

- 调 `Mt/Nt/Kt`
- 增大 N tile 数据复用
- L0A/L0B Double Buffer
- 必要时 K>4096 测一次 staggered / MDL

#### 情况 B：Cube 和 Vector 串行明显

做：

```text
Cbuf0 / Cbuf1 Ping-Pong
```

目标：

```text
Cube:   GEMM0 | GEMM1 | GEMM2
Vector:         MAX0  | MAX1  | MAX2
```

让时间从：

```text
Cube + Vector
```

尽量接近：

```text
max(Cube, Vector)
```

#### 情况 C：某一种 transpose layout 特别慢

只给该 layout 单独一个 TilingKey / tile 配置，不重写 kernel。

---

## 3. 最终结构

只保留下面这个版本族：

```text
                     Host Tiling
                         │
                shape + layout
                         │
              ┌──────────┴──────────┐
              ↓                     ↓
      Main B/M Streaming        Split-N
              │                     │
              └──────────┬──────────┘
                         ↓
                 Cube GEMM Tile
                         ↓
                 Vector RowMax
                         ↓
                    Sum / partial
                         ↓
                       y[B]
```

最终真正需要维护的只有：

1. **Main Streaming Kernel**：覆盖绝大多数 case。
2. **Split-N Kernel**：补小 B、小 M、大 N。
3. **Tiny Final Reduce**：处理 partialY / partialMax。

不要同时开发 8~9 套 kernel。

---

## 4. 明确不做的东西

当前时间有限，以下全部后置：

- Strassen / Winograd
- Split-K
- 独立 Tiny Vector Kernel
- 复杂 Stream-K
- IBShare
- 多套 K-heavy kernel
- 大范围 autotune
- 针对每个 shape 写一套实现

除非 profiler 明确证明主瓶颈就在这里，否则不碰。

---

## 5. 开发顺序

实际只需要三轮：

### 第一轮：正确 + 融合

```text
Streaming GEMM → Max → Sum
+
Batch/M 分核
+
四种 layout
+
所有 tail 正确
```

目标：所有 15 case 先过精度，并拿到融合的大头收益。

### 第二轮：补低 occupancy

```text
增加 Split-N
```

只解决 V8.0 明显慢的“小 B、小 M、大 N”测试点。

### 第三轮：Profiler 定向冲刺

只看最差的 3~5 个 case：

```text
msprof
→ 判断 Cube / Vector / MTE / occupancy
→ 调 tile 或加 Ping-Pong
→ 再测
```

不再扩展算法树。

---

## 6. 一句话版本

本次冲榜直接押注：

\[
\boxed{
\text{Streaming Cube→Vector Fusion}
+
\text{Split-M 主路径}
+
\text{Split-N 兜底}
+
\text{一次 Profiler 定向优化}
}
\]

优先把完整 `B×M×N` 中间矩阵从 GM 中消灭掉；这是这道题最值得投入时间的结构性优化。

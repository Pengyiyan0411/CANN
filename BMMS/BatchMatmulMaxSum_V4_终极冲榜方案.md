# BatchMatmulMaxSum V4：终极冲榜方案

> 目标：在保证 **15 个测试点全部正确** 的前提下，针对昇腾 A2 / CANN 9.0 做极限性能优化。  
> 核心思想：不再把问题当成“一个融合 MatMul 算子”，而是构建一个 **Shape-Aware Kernel Portfolio + 解析/离线 Autotune Dispatcher**，让不同 `(B,M,N,K,layout,dtype)` 走不同最优执行路径。

---

# 1. 题目本质

数学语义固定为：

\[
A[b,m,n]
=
\sum_{k=0}^{K-1}
X_1[b,m,k]X_2[b,k,n]
\]

\[
R[b,m]
=
\max_n A[b,m,n]
\]

\[
y[b]
=
\sum_m R[b,m]
\]

即：

```text
BatchMatMul
    ↓
Max over N
    ↓
Sum over M
    ↓
y[B]
```

必须满足：

- `x1 logical shape = [B,M,K]`
- `x2 logical shape = [B,K,N]`
- `y = [B]`
- x1/x2：FP16 或 BF16
- K 维点积：FP32 累加或等效精度
- Max：FP32
- Sum：FP32
- 顺序必须严格是 `MatMul → Max(N) → Sum(M)`
- `Max` 初值必须是 `-INF` 或首有效值
- 四种 storage layout 都要支持
- M/N 非 16 对齐尾块必须正确
- 相同输入多次运行结果必须一致

---

# 2. V4 总体定位

V4 不再追求：

> 一个 kernel 打遍所有 case

而是：

```text
                    Host Shape Classifier
                           │
         ┌─────────────────┼────────────────────┐
         │                 │                    │
       Dense             Skinny              Tiny-BMM
         │                 │                    │
    2D Cube Grid        AIV FMA            IterateBatch
         │
  choose pM × pN
         │
 choose stationary
      A or B
         │
 choose Matmul template
 BasicBlock / MDL / ...
         │
 static K specialization
  32 / 64 / 128 / ...
         │
 Cube → UB
         │
 online RowMax
         │
 partialMax
         │
     deterministic merge
         │
        y[B]
```

核心思想：

> **数据流优先，而不是算术优先。**

---

# 3. 最大结构升级：M×N 二维分核

## 3.1 为什么不再默认只切 M

若 B 很小，例如：

```text
B = 1
M = 8192
N = 8192
```

如果 24 个核全部沿 M 切：

```text
24 × 1
```

那么同一份 `X2` 会被很多核重复读取。

反之，只沿 N 切：

```text
1 × 24
```

则 `X1` 被大量重复读取。

因此采用：

\[
p_M \times p_N \approx q
\]

其中 `q` 是当前 batch 可用 AIC 数。

每个核负责：

\[
M_s \times N_s
\]

局部区域。

---

## 3.2 理论数据搬运模型

忽略 cache 后，输入读取量近似：

\[
Bytes_{\text{input}}
\propto
2BK(Mp_N+Np_M)
\]

其中 FP16/BF16 元素 2 字节。

因此优化：

\[
\min_{p_Mp_N=q}
Np_M + Mp_N
\]

连续近似解：

\[
p_M \approx \sqrt{\frac{Mq}{N}}
\]

\[
p_N \approx \sqrt{\frac{Nq}{M}}
\]

---

## 3.3 24 AIC 的候选网格

起始候选：

| M/N 比例 | 初始候选 |
|---|---|
| `< 1/12` | `1×24` |
| `1/12 ~ 1/4` | `2×12` |
| `1/4 ~ 1/2` | `3×8` |
| `1/2 ~ 1` | `4×6` |
| `1 ~ 2` | `6×4` |
| `2 ~ 4` | `8×3` |
| `4 ~ 12` | `12×2` |
| `> 12` | `24×1` |

这只是 autotune 起点，不是硬编码。

---

# 4. 2D 分核后的正确归约

每个 worker：

```text
(b, mShard, nShard)
```

负责：

```text
X1[b, M_local, K]
×
X2[b, K, N_local]
```

得到局部：

\[
r_{i,j}(m)
=
\max_{n\in N_j} A[m,n]
\]

写入：

```text
partialMax[b][mShard][nShard][mLocal]
```

Phase 1：

```text
Cube / Vector
↓
local Max(N_local)
↓
partialMax
```

然后：

```text
SyncAll<false>()
```

Phase 2：

\[
r(m)=\max_j r_j(m)
\]

再：

\[
y[b]=\sum_m r(m)
\]

整个过程严格保持：

```text
Max(N)
↓
Sum(M)
```

---

# 5. partialMax Workspace 很小

极端：

```text
M = 8192
pN = 24
```

FP32 workspace：

\[
8192\times24\times4
=
786432B
\]

约：

```text
768 KiB
```

而完整 `[8192,8192]` FP32 相似度矩阵约：

```text
256 MiB
```

因此 2D 分核引入的 partialMax 成本非常小。

---

# 6. 每个核动态选择 A-stationary / B-stationary

设当前核负责：

\[
A_s=[M_s,K]
\]

\[
B_s=[K,N_s]
\]

## 6.1 A-stationary

若：

\[
M_sK \times 2
\]

更适合驻留 L1：

```text
X1 shard
   ↓
驻留 L1
   ↓
B tile 0
B tile 1
B tile 2
...
```

适合：

```text
M_s 较小
N_s 较大
```

---

## 6.2 B-stationary

若：

\[
KN_s \times 2
\]

更适合驻留：

```text
X2 shard
   ↓
驻留 L1
   ↓
A tile 0
A tile 1
A tile 2
...
```

适合：

```text
N_s 较小
M_s 较大
```

---

## 6.3 双方都能驻留

若：

```text
A_s + B_s
```

都能在 L1 合理驻留：

```text
GM
 ↓ 一次
L1
 ↓
反复 MTE1 → L0
```

这是最理想路径。

---

# 7. L2 Cache 策略

不能把 L2 当黑盒。

## pM 大、pN 小

例如：

```text
24×1
```

大量核共享 X2。

优先：

```text
X2 → Cache
X1 → Stream / Disable candidate
```

---

## pM 小、pN 大

例如：

```text
1×24
```

大量核共享 X1。

优先：

```text
X1 → Cache
X2 → Stream / Disable candidate
```

---

## 2D Grid

例如：

```text
4×6
```

X1 复用约 6 次，X2 复用约 4 次。

根据：

```text
reuse_count × tensor_size
```

决定 cache 优先级。

需要 A/B 实测：

```text
CACHE_BOTH
CACHE_X1
CACHE_X2
```

---

# 8. Diagonal / Wavefront Core Mapping

不要简单：

```text
core0 → (m0,n0)
core1 → (m1,n0)
core2 → (m2,n0)
...
```

否则多个核会同时访问同一 X2 shard。

采用对角线：

```text
core0 → (0,0)
core1 → (1,1)
core2 → (2,2)
core3 → (3,3)
...
```

或：

```text
nShard = (physicalCore + mShard * shift) % pN
```

目标：

- 降低同址访问冲突
- 分散 MTE2 峰值
- 改善 L2 port contention

需要 A/B：

```text
ROW_MAJOR
vs
DIAGONAL
```

---

# 9. 512B-aware Shard Boundary

A2 GM 搬运对 512B 对齐敏感。

FP16/BF16：

```text
512B / 2B = 256 elements
```

因此 shard 边界不只考虑：

```text
load balance
```

还考虑：

```text
byteOffset % 512 == 0
```

注意四种 storage layout 下实际 stride 不同。

Host 根据：

```text
real storage shape
real byte stride
```

枚举若干邻近 shard boundary，选择：

```text
综合负载均衡 + 对齐更好的方案
```

---

# 10. Cube Tile 候选

不能固定一个 tile。

主要候选：

| Tile `(M,N,K)` | FP32 C 大小 | 定位 |
|---|---:|---|
| `128×256×64` | 128 KB | Cube/MTE 优先 |
| `128×128×128` | 64 KB | 平衡 |
| `128×128×64` | 64 KB | 小/中 K |
| `64×256×64` | 64 KB | 中小 M |
| `32×256×64` | 32 KB | 2AIV / skinny-ish |

---

# 11. K 专用静态微内核

必须重点特化：

```text
K = 32
K = 64
K = 128
K = 256
K >= 512
```

---

## 11.1 K=32

单独路径：

```text
baseK = 32
singleCoreK = 32
```

目标：

```text
无 K loop
无 K tail
尽量无运行时条件
```

这类 case 很容易被：

```text
Scalar
sync
Matmul init
MTE
```

限制，而不是 Cube 算力。

---

## 11.2 K=64 / 128

编译期固定：

```text
SpecialBasicBlock
static tiling
```

热点循环里尽量消除：

```text
if
SetTail
动态 tiling 参数计算
```

---

## 11.3 大 K

重点使用：

```text
MDL
KdimReorderLoad candidate
MTE2 preload candidate
```

---

# 12. Main Body / Tail Epilogue 分离

不要每个 tile 都：

```cpp
if (tailM)
if (tailN)
if (tailK)
```

设计：

```text
MAIN_BODY
---------
全对齐
静态 tile
无分支

TAIL_EPILOGUE
-------------
只处理最后 M/N/K 尾块
```

例如：

```text
N = 8195
```

前：

```text
8192
```

走极致 main kernel。

最后：

```text
3
```

走 generic tail。

---

# 13. Max Reduction 设计

核心状态：

```text
runningMax[M_local]
```

FP32。

初始化：

```text
-INF
```

流程：

```text
C tile
↓
RowMax over valid N
↓
blockMax[M_tile]
↓
runningMax = max(runningMax, blockMax)
```

---

## 两套 reduction microkernel

### R0

```text
WholeReduceMax
↓
runningMax
```

### R1

```text
BlockReduceMax
↓
Second Reduce
↓
runningMax
```

根据：

```text
Ntile = 64 / 128 / 256
```

真机 A/B。

---

# 14. NZ-native RowMax

Cube C 尽量保持 NZ/fractal。

不要：

```text
NZ → ND → Max
```

而直接：

```text
NZ fractal
↓
N0=16 local reduction
↓
across-N1 reduction
↓
row max
```

一个 16×16 fractal：

```text
16 行
每行 16 元素
```

先每行得到一个局部 max，再与下一个 N fractal 合并。

最终只长期保留：

```text
runningMax[M_local]
```

---

# 15. UB Bank Conflict 优化

重点对象：

```text
C0
C1
runningMax
reduceScratch
```

不能简单连续摆放。

实验：

```text
offset:
0
32B
64B
96B
128B
```

观察：

```text
UB Read BW
UB Write BW
AIV active
task duration
```

---

# 16. Persistent Worker

一个物理 worker：

```text
获取自己的 (b,mShard,nShard)
↓
整个 shard 一次做完
↓
写一次 partialMax
```

不是：

```text
one tile = one task
```

好处：

- runningMax 长期驻 UB
- shard metadata 常驻寄存器
- Matmul object 不反复初始化
- L1 stationary 更自然
- 更容易做 staggered traversal

---

# 17. N-tile Phase Staggering

即使 2D grid 内，同一列/行仍可能出现同址冲突。

每个 worker：

```cpp
start = hash(mShard, nShard) % nTileCount;

for i in [0, nTileCount):
    nt = (start + i) % nTileCount;
```

Max 对 tile 顺序不敏感，因此合法。

A/B：

```text
SYNC_ORDER
vs
STAGGER_ORDER
```

---

# 18. MDL 路径

适用：

```text
local shard 大
MTE2 占比较高
L1 存在明显复用
```

建议初始 candidate：

```text
baseM = 128
baseN = 256
baseK = 64
```

测试：

```text
stepM = 1 / 2 / 4
stepN = 1 / 2
```

核心原则：

> 让 stationary operand 在 L1 尽量服务更多 base block。

---

# 19. KdimReorderLoad

候选条件：

```text
K >= 4096
A/B 无法全部驻留 L1
多核同时大量访问相同 K 地址
```

A/B：

```text
OFF
vs
ON
```

主要观察：

```text
MTE2 duration
total task duration
```

---

# 20. MTE2 Preload

只在满足官方使用条件时测试：

```text
MDL / SpecialMDL
K 方向全载
对应 M/N 方向具备 Double Buffer
```

A-stationary：

```text
预取下一 N packet
```

B-stationary：

```text
预取下一 M packet
```

---

# 21. 1 AIC : 2 AIV 路径

不是所有 case 都开启。

适合：

```text
Vector reduction 比较重
M 够大
共享 B 有价值
```

逻辑：

```text
        shared X2 / B
             │
          L1 Share
          /      \
       AIV0      AIV1
      M前半      M后半
        │          │
     RowMax      RowMax
        │          │
     Sum0        Sum1
```

重点结合：

```text
IBShare-B
```

测试：

```text
1:1
vs
1:2 + IBShare
```

---

# 22. Skinny-AIV：极细矩阵不用 Cube

这是 V4 的高风险高收益实验路径。

重点 shape：

```text
M = 1 / 2 / 4 / 8
K = 32 / 64
N >= 512
```

尤其：

```text
transposeX2 = false
X2 storage = [K,N]
```

固定 k 时：

```text
X2[k, :]
```

沿 N 连续。

Vector 直接：

```text
scores[Ntile] = 0

for k:
    a = broadcast(X1[m,k])
    b = load X2[k, Ntile]
    scores += a * b

rowMax = max(scores)
```

优势：

```text
无 Cube setup
无 AIC↔AIV Matmul 消息
无 NZ C
无 GetTensorC
无 FixPipe 后再 reduction
```

是否赢必须实测。

---

# 23. Tiny-N AIV Path

若：

```text
N = 1 / 2 / 4
```

Max 几乎消失。

任务更接近：

```text
多个 K-dot
↓
Sum M
```

同样测试：

```text
AIV dot
vs
tiny Cube
```

---

# 24. Batch-Tiny：IterateBatch

重点：

```text
B 大
M/N 小
```

例如：

```text
B=64
M=8
N=32
K=128
```

不要做：

```text
64 次 tiny Matmul launch/communication
```

而是：

```text
多个 b
↓
IterateBatch
↓
Batch C
↓
MaxSum
```

专门 kernel：

```text
BATCH_TINY
```

---

# 25. N-shard Path

如果：

```text
B×可用M并行
```

不足以填满 AIC，而 N 很大：

```text
split N
```

每个 shard：

```text
local Max
↓
partialMax
```

之后：

```text
Max across N shards
↓
Sum M
```

---

# 26. 极端 K-shard

只用于：

```text
M,N 极小
K 极大
```

例如：

```text
B=1
M=1
N=1
K=8192
```

此时 M/N 都没法提供并行度。

每个核：

```text
K shard
↓
partial C
```

Phase 2：

```text
按固定 shard 顺序 FP32 Sum
↓
Max N
↓
Sum M
```

不要使用不确定顺序的 FP32 AtomicAdd。

---

# 27. 不使用完整 C Workspace

主路径目标：

```text
GM
 ↓
L1
 ↓
L0A / L0B
 ↓
MMAD
 ↓
L0C FP32
 ↓
VECIN / UB
 ↓
RowMax
```

禁止：

```text
完整 [M,N] C
↓
GM
↓
再读回来 Max
```

---

# 28. Sync / Async GetTensorC

必须作为实验项，而不是理论决定。

## Sync

优点：

```text
无额外 GM workspace
```

缺点：

```text
Cube / Vector sync 可能多
```

## Async

优点：

```text
可能减少 pipeline stall
```

缺点：

```text
需要 GM workspace
可能重新引入 C traffic
```

测试：

```text
K = 32
64
128
512
4096
```

---

# 29. 四种 Storage Layout

逻辑永远：

```text
x1: [B,M,K]
x2: [B,K,N]
```

storage：

```text
FF:
x1 [B,M,K]
x2 [B,K,N]

FT:
x1 [B,M,K]
x2 [B,N,K]

TF:
x1 [B,K,M]
x2 [B,K,N]

TT:
x1 [B,K,M]
x2 [B,N,K]
```

不要运行时热点循环大量：

```cpp
if (transposeX1)
if (transposeX2)
```

编译：

```text
FP16_FF
FP16_FT
FP16_TF
FP16_TT

BF16_FF
BF16_FT
BF16_TF
BF16_TT
```

Host 通过：

```text
TilingKey
```

选择。

---

# 30. Correctness 红线

## 30.1 Max 初值

必须：

```text
-INF
```

绝不能：

```text
0
```

---

## 30.2 N tail

最后 N tile 无效 lane：

```text
-INF
```

不能：

```text
0
```

---

## 30.3 K accumulation

必须：

```text
FP32 accumulation
```

---

## 30.4 归约顺序

必须：

```text
Max N
↓
Sum M
```

绝不能交换。

---

## 30.5 Batch

必须：

```text
x1[b] ↔ x2[b]
```

不允许广播或 cross-batch。

---

## 30.6 Determinism

不依赖：

```text
FP32 AtomicAdd
```

随机执行顺序。

---

# 31. 最终 Dispatcher

```cpp
Strategy SelectStrategy(shape, layout, dtype)
{
    if (isTinyPair(shape) && B_is_large) {
        return BATCH_TINY;
    }

    if (isSkinny(shape)) {
        if (vectorPathEstimatedBetter())
            return SKINNY_AIV;
    }

    if (enoughDenseParallelism()) {
        Grid grid = choose2DGrid();

        Stationary st = chooseStationary(grid);

        MatmulTemplate mt = chooseMatmulTemplate(
            K,
            localM,
            localN,
            l1Capacity,
            profileTable
        );

        return DENSE_2D;
    }

    if (N_has_parallelism()) {
        return N_SHARD;
    }

    if (K_is_huge && M*N_is_tiny) {
        return K_SHARD;
    }

    return GENERIC_SAFE;
}
```

---

# 32. Cost Model

初始估计：

\[
T_{est}
=
\max(
T_{cube},
T_{memory}
)
+
T_{vector}
+
T_{sync}
\]

其中：

\[
FLOPs = 2BMNK
\]

二维输入流量：

\[
Bytes_{input}
=
2BK(Mp_N + Np_M)
\]

partialMax 读写：

\[
Bytes_{partial}
\approx
8BMp_N
\]

然后用真机 profile 拟合：

```text
effectiveCubeEfficiency
effectiveMTEBandwidth
vectorPenalty
pNMergePenalty
layoutPenalty
tailPenalty
```

---

# 33. 离线 Autotune 搜索空间

不要全笛卡尔积暴搜。

候选：

| 参数 | candidates |
|---|---|
| grid | `24×1,12×2,8×3,6×4,4×6,3×8,2×12,1×24` |
| tileM | 16 / 32 / 64 / 128 |
| tileN | 64 / 128 / 256 |
| tileK | 32 / 64 / 128 |
| template | Norm / BasicBlock / MDL / SpecialMDL |
| stationary | A / B |
| L2 | X1 / X2 / Both |
| mapping | RowMajor / Diagonal |
| N order | Normal / Stagger |
| reduction | Whole / Block+Whole |
| AIV | 1 / 2 |
| C mode | Sync / Async |
| kernel | Cube / Skinny-AIV / Batch |

---

# 34. Autotune 剪枝

先剔除：

```text
UB 超容量
L1 超容量
tile 与 layout 不合理
M/N shard 太小
pN merge 成本过大
```

再用解析模型选 Top-K：

```text
Top 3~5 configs
```

真机 profile。

---

# 35. 必测代表 Shape

至少：

```text
1×32×256×128
1×128×512×128
1×1024×1024×128
1×2049×8192×32
1×8192×8192×32

1×64×64×8192
1×1×8192×128
1×1×1×8192

8×32×256×128
64×8×32×128
```

额外：

```text
M/N 非16倍数
K=32
K=64
FP16
BF16
FF / FT / TF / TT
全负输入
```

---

# 36. 实验优先级

## S 级

### E1：M-only vs 2D Grid

测试：

```text
24×1
12×2
8×3
6×4
4×6
3×8
2×12
1×24
```

指标：

```text
Task Duration
MTE2
L2
MAC utilization
```

---

### E2：A-stationary vs B-stationary

重点：

```text
M >> N
N >> M
M ≈ N
```

---

### E3：K32 / K64 静态 kernel

比较：

```text
Generic
BasicBlock
SpecialBasicBlock
```

---

## A 级

### E4：L2 Hint

```text
CACHE_BOTH
CACHE_X1
CACHE_X2
```

### E5：Core Mapping

```text
RowMajor
Diagonal
```

### E6：512B-aware shard

```text
Balanced
Aligned
```

### E7：Skinny-AIV

```text
M = 1/2/4/8
K = 32/64
```

### E8：BasicBlock vs MDL

---

## B 级

### E9：1:1 vs 1:2 + IBShare

### E10：N order

```text
Normal
Staggered
```

### E11：KdimReorderLoad

### E12：MTE2 preload

### E13：Sync vs Async

---

## C 级

### E14：手写 low-level Cube

只有 profile 显示：

```text
Scalar / sync / high-level API overhead
```

确实是主要瓶颈时再做。

---

# 37. Profiling 指标

每次实验记录：

```text
Task Duration
AIC MAC utilization
AIC active
AIC MTE2 duration
AIV active
Vector duration
Scalar duration
UB bandwidth
L2 hit / miss
```

诊断：

```text
MAC低 + MTE2高
→ 数据流 / L2 / stationary / MDL

AIC快 + AIV拖尾
→ reduction / 1:2 AIV / UB bank

Scalar高
→ static kernel / BasicBlock / Batch

核利用率低
→ 2D / N-shard / K-shard

tiny shape慢
→ Skinny-AIV / IterateBatch
```

---

# 38. 实现顺序

## Stage 0：稳定 baseline

先保证：

```text
所有 case 100% 正确
```

包括：

```text
FP16/BF16
FF/FT/TF/TT
tail
negative
large K
```

---

## Stage 1：2D Grid

优先实现：

```text
pM × pN
partialMax
deterministic Phase2
```

这是最大结构升级。

---

## Stage 2：Stationary + L2

实现：

```text
A-stationary
B-stationary
L2 hint
diagonal mapping
```

---

## Stage 3：Static K

```text
K32
K64
K128
```

---

## Stage 4：Matmul Template

```text
BasicBlock
MDL
SpecialMDL
```

---

## Stage 5：特殊 Kernel

```text
Skinny-AIV
Batch-Tiny
N-shard
K-shard
```

---

## Stage 6：微优化

```text
UB bank
stagger
MTE2 preload
K reorder
sync/async
```

---

## Stage 7：Low-level Cube

只针对真正热点 case。

---

# 39. 代码目录建议

```text
batchmatmulmaxsum/
│
├── host/
│   ├── tiling.cpp
│   ├── cost_model.cpp
│   ├── strategy_selector.cpp
│   └── profile_table.h
│
├── kernel/
│   ├── dense_2d/
│   │   ├── k32.asc
│   │   ├── k64.asc
│   │   ├── k128.asc
│   │   ├── generic.asc
│   │   └── reduction.asc
│   │
│   ├── skinny/
│   │   └── skinny_aiv.asc
│   │
│   ├── batch/
│   │   └── iterate_batch.asc
│   │
│   ├── shard/
│   │   ├── n_shard.asc
│   │   └── k_shard.asc
│   │
│   ├── tail/
│   │   └── generic_tail.asc
│   │
│   └── common/
│       ├── layout.h
│       ├── reduce.h
│       └── sync.h
│
└── benchmark/
    ├── cases.json
    ├── run_profile.sh
    ├── parse_profile.py
    └── autotune.py
```

---

# 40. 最终推荐主路径

当前最值得押注：

```text
Adaptive 2D Grid
+
Persistent Worker
+
A/B Stationary
+
L2-aware operand policy
+
Diagonal Core Mapping
+
512B-aware shard
+
Static K32/K64/K128
+
BasicBlock / MDL auto selection
+
Cube → VECIN / UB
+
NZ-native RowMax
+
runningMax FP32
+
partialMax
+
SyncAll
+
deterministic Max(pN) → Sum(M)
```

特殊 shape：

```text
Skinny
→ AIV FMA

B大、单pair小
→ IterateBatch

并行不足 + N大
→ N-shard

M/N极小 + K巨大
→ deterministic K-shard
```

---

# 41. 最关键的三个新竞争点

## 1. 2D `pM×pN` 分核

不再把 X1 或 X2 的重复读取全部压到一边。

这是目前最大的结构升级。

---

## 2. L1 Stationary + L2-aware + Diagonal Mapping

明确控制：

```text
谁驻 L1
谁进入 L2
谁按 stream 访问
物理核以什么顺序访问
```

而不是让硬件默认处理全部复用。

---

## 3. K32/K64 Static + Skinny-AIV

真正容易拉开隐藏 case 差距的，往往不是标准大 GEMM，而是：

```text
小 K
细长 M/N
小 batch matrix
```

这些 shape 必须用专用 kernel。

---

# 42. 当前结论

V4 的目标不再是：

> 写一个“更快的 MatMulMaxSum kernel”。

而是：

> **建立一个小型 kernel portfolio，让每类 shape 都使用最适合它的数据流、并行方式和硬件单元。**

最终真正冲榜的核心是：

```text
算法语义不变
↓
数据流重构
↓
2D 并行
↓
片上驻留
↓
硬件资源匹配
↓
静态特化
↓
离线 autotune
```

这是目前最值得继续实现和实验的版本。

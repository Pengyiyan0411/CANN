有，而且信息量其实比表面看起来更大。最关键的是：**这轮把“第七个短 K-stage”这个假说直接排除了，同时把 B 的实际布局钉死了。**

以 `113.67 μs` baseline 为参照：

| 探针             | C12        | 结论                         |
| ---------------- | ---------- | ---------------------------- |
| `K_GE_1568`      | 113.94 μs  | **NO → K=1536**              |
| `K_GE_1632`      | 不需要再跑 | P1 已经确定 K=1536           |
| `TB_TRUE`        | 113.95 μs  | **NO → TB=false**            |
| `TAIL_B_LOAD_X2` | 114.55 μs  | 实际上**没有触发 tail 分支** |
| `TAIL_A_LOAD_X2` | 114.90 μs  | 同样**没有触发 tail 分支**   |

### 最重要的是第一条：Case12 的 K 已经精确确定为 1536

因为我们原来已经知道：

\[ K\in\{1536,1568,1600,1632\}. \]

而 `K_GE_1568` 没有出现 1.4 ms 级别的强 HIT，只是：

\[ 113.67\rightarrow113.94\mu s, \]

所以 predicate 为 false：

\[ \boxed{K=1536}. \]

因此当前：

\[ K_1=256 \]

恰好是：

\[ 1536/256=6 \]

个完整 stage：

\[ k_0=0,256,512,768,1024,1280. \]

**根本不存在 `k0==1536` 的第七 stage。**

这意味着 P4/P5 的：

```
if (... && k0 == 1536)
    DataCopy(...);
```

一次都没有执行。

所以：

\[ 114.55,\quad114.90 \]

不能解释成“tail A/B load 只有 +0.9/+1.2 μs”。

正确解释是：

\[ \boxed{\text{P4/P5 是结构性 negative control，证明不存在 seventh-stage tail。}} \]

那一两微秒就是不同 build/run 的漂移量级。

这也说明我们之前关于“最后 32/64/96 个 K 导致完整第七 stage”的方向，现在可以**正式删除**。

------

### 第二个很重要的信息：`TB=false`

`TB_TRUE` 同样完全没有强 HIT，因此：

\[ \boxed{TB=false}. \]

这对下一步非常有价值，因为当前 `LoadStage()` 在 `TB=false` 时会退化成明确的：

```
qb.nValue = kr;
qb.dValue = br;
qb.srcDValue = p.N;

bi = batch*K*N + k0*N + n0;
```

也就是说 B 的源 panel 本质上是：

\[ \boxed{K_{\text{slab}}\times N_{\text{stripe}}} \]

每个 K row 中取一段连续的 N 区域，而相邻 row 之间按照完整 `N` stride 前进。源码就是这样构造 B 的 `Nd2Nz DataCopy`。

这比“TB 可能真可能假”好很多，因为后面可以直接针对 **TB=false 的宽 N panel** 写专用 producer，不必首先兼顾另一种物理布局。

------

## 现在对 `K1=320` 的理解也要修正

我仍然认为它值得测试，但**理由已经变了**。

之前考虑 `K1=320`，部分动机是消掉第七个短 tail stage。

现在我们知道：

\[ K=1536, \]

本来就没有 tail。

所以当前：

\[ K_1=256 \Rightarrow 6\text{ stages} \]

如果改：

\[ K_1=320, \]

会变成：

\[ 320+320+320+320+256=1536 \]

即：

\[ \boxed{5\text{ stages}}. \]

它测试的就变成了一个更纯粹的问题：

> **在总 A/B 字节数基本不变的情况下，减少一次 LoadStage/event/pipeline 周期是否能提高性能？**

这其实是个很好的机制实验。

因为我们已经知道：

\[ A\_LOAD\_X2:+21.9\mu s, \]\[ B\_LOAD\_X2:+33.0\mu s. \]

但这些结果还不能区分：

\[ \text{总带宽成本} \]

和

\[ \text{每 stage 的 setup/event/pipeline 成本}. \]

现在直接做 `K1` 粒度实验，比继续设计 timing probe 更有价值。

------

## 我建议下一轮已经不要叫“探针轮”了，而是第一次 optimization sweep

最干净的是只做三个版本：

\[ K_1=192,\qquad256,\qquad320. \]

因为 Case12 的：

\[ K=1536 \]

已经精确知道。

这样：

\[ K_1=192\Rightarrow8\text{ stages}, \]\[ K_1=256\Rightarrow6\text{ stages}, \]\[ K_1=320\Rightarrow5\text{ stages}. \]

总语义工作量和总 K 长度都一样。

如果实测出现：

```
K1=192    120 us
K1=256    113.7 us
K1=320    106 us
```

那证据就非常漂亮：

\[ \boxed{\text{stage granularity / feeding pipeline overhead 很重要}} \]

我们就继续放大 K1。

反过来，如果：

```
192       114
256       113.7
320       114
```

说明前面的 A/B sensitivity 主要反映的是：

\[ \boxed{\text{数据量 / 搬运吞吐，而不是 stage 数}} \]

那就应该停止调 K1，直接进入 **B reuse / B-load specialization**。

------

### 这里还有一个资源上的现实约束

当前 A1+B1 双缓冲规模大致正比于：

\[ 2K_1(AM+BN). \]

现在：

\[ AM=128,\quad BN=256. \]

对于 FP16/BF16 的 2-byte 元素，只算 A1+B1：

\[ K_1=256\Rightarrow384\text{ KiB} \]\[ K_1=320\Rightarrow480\text{ KiB} \]\[ K_1=384\Rightarrow576\text{ KiB}. \]

所以 `320` 是值得实际编译试的，而 `384` 已经明显更激进；在没有确认实际资源允许之前，我不会直接把 384 当正式候选。

------

## 更重要的是：如果 K1 sweep 没明显收益，下一刀已经非常清楚

因为现在我们已经有：

\[ \boxed{TB=false} \]

并且：

\[ \boxed{B\_LOAD\_X2\text{ 是所有 sensitivity 中最强的}} \]

那么下一步应该专门针对当前这种 B panel：

\[ B[k_0:k_0+kr,\ n_0:n_0+br] \]

做搬运优化，而不是继续碰 rowmax / merge。

当前每个 macro 都重新执行一次 A/B `LoadStage`，并用 `Nd2Nz DataCopy` 把 panel 喂进 L1；随后才进入 L0 load 和 MMAD。

所以真正值得问的已经是：

\[ \boxed{\text{能否减少 B panel 被不同 macro 重复搬运，或者提高 TB=false 时单次 B panel 的搬运效率？}} \]

这比继续优化 consumer 的收益上限明显高得多。

------

所以这轮结果不是“没探到东西”。

恰恰相反，它完成了三个非常关键的收敛：

\[ \boxed{K=1536} \]\[ \boxed{TB=false} \]\[ \boxed{\text{不存在 seventh-stage tail}} \]

因此 Case12 的主线现在可以正式从：

> “是不是 K-tail / reduction / planner 导致慢？”

切换成：

\[ \boxed{\textbf{为什么 6 个完整 K stages 下，A/B operand feeding 尤其是 B feeding 仍然占据关键路径？}} \]

我认为**到这里可以停止诊断探针了**。下一步直接做 `K1=192/320` 两个性能版本，以 256 为 baseline；这个结果一出来，就能决定是继续优化 stage pipeline，还是直接进入 TB=false 的 B-reuse 专用 kernel。

​    

现总结一下现有的信息，然后后面值得考虑的方面是什么，总结一下

 



思考了 52s

可以把 Case12 目前的状态收成一个比较清楚的“诊断冻结版”。现在已经不是还在到处猜瓶颈，而是已经把问题压缩到了 **producer 侧 operand feeding，尤其是 B feeding**。

## 1. 目前已经确定的事实

| 层面                   | 已确定信息                                         | 证据/含义                                               |
| ---------------------- | -------------------------------------------------- | ------------------------------------------------------- |
| 当前性能               | baseline 约 **113.67 μs**，最优参考 **89.22 μs**   | 仍有约二十多微秒空间                                    |
| 当前路由               | Case12 当前走 **`bmms1230`**                       | R30 stress 后 Case12 变成约 1.43 ms                     |
| r41 eligibility        | shape 范围满足，`AlignedPitch=true`                | 不是 shape/layout 把它挡掉                              |
| r41 gate               | **`flatPeak == oldPeak`**                          | `FLAT_EQ_OLD` HIT，`FLAT_GT_OLD` NO                     |
| r41 实际效果           | `ALLOW_TIE` 两次约 **117.01 / 116.88 μs**          | 比 baseline 稳定慢约 3 μs，因此不应简单把 `<` 改成 `<=` |
| 并行计划               | **`pN=2`**，`pM>=8`，`tasks=cores`，`blocks=cores` | 当前已经 full-occupancy、single-wave，不是并行不足      |
| K                      | **K=1536**                                         | `K_GE_1568` NO                                          |
| K pipeline             | 当前 `K1=256`，因此正好 **6 个完整 stage**         | 不存在第 7 个短 tail stage                              |
| B layout               | **`TB=false`**                                     | `TB_TRUE` NO                                            |
| A load sensitivity     | `A_LOAD_X2 = 135.58 μs`                            | 相比 baseline 约 +22 μs，强信号                         |
| B load sensitivity     | `B_LOAD_X2 = 146.66 μs`                            | 相比 baseline约 +33 μs，当前最强信号                    |
| ring handoff           | `RINGREAD_X2 = 118.39 μs`                          | 有影响，但明显弱于 A/B load                             |
| partial / merge / sync | 约 115 μs                                          | 只有弱信号                                              |
| rowmax                 | **113.67 μs**                                      | 几乎无敏感度                                            |

当前 `bmms1230` 的 producer 对每个 macro 都重新执行 A/B 的 `Nd2Nz DataCopy`，随后进入 L0 load 和 MMAD；空间循环又是 `m0` 外层、`n0` 内层。 

所以目前最合理的结构性判断是：

\[ \boxed{ \text{Case12 主要矛盾在 A/B operand-feeding pipeline，且 B 侧最值得优先处理。} } \]

注意这里的 sensitivity 增量不能当作严格的时间占比，因为重复 DMA 会改变流水 overlap；但它们的**相对排序**已经非常有辨识度。

------

## 2. 现在已经可以暂时排除哪些方向

有几条路线现在不值得继续当主线了。

**第一，不是 core 数不足。** 当前 `tasks=blocks=cores`，而且 single-wave，所以不是简单增加并行度就能解决。

**第二，不是 pN 过大。** `pN=2` 已经很温和，因此原先“wide-N 导致很多 N shard，最后 merge 很重”的猜测基本不成立。

**第三，不是 reduction/rowmax。** `ROWMAX_X2` 几乎完全不动，partial、merge、SyncAll 也只有约 1–2 μs 的变化。当前 consumer 虽然确实要做 ring read、row max、partial 和最终跨 `pN` merge， 但它们不是当前二十多微秒性能缺口的主要解释。

**第四，不是 K tail。** `K=1536=6×256`，所以当前六个 stage 全是完整 stage。之前怀疑的“为了最后 32/64/96 个 K 又启动一次昂贵 stage”已经被排除。

**第五，也不是简单扩大 r41 覆盖范围。** Case12 恰好是 peak tie，而真正让它进入 r41 后反而稳定慢约 3 μs。所以当前 `<` gate 至少在 Case12 上是合理的。

------

# 3. 现在真正剩下的核心问题

可以把它压缩成一句：

> **为什么在一个 full-occupancy、single-wave、K=1536、pN=2 的规整 workload 上，六个完整 K stage 的 operand feeding 仍然不能被计算充分隐藏，尤其为什么 B feeding 表现出最强敏感性？**

这个问题比“Case12 怎么调快”更有用，因为它直接决定下一代 kernel 应该改哪一层。

现在主要有三种可能：

\[ \textbf{A. stage/setup 开销} \]

也就是每一次 `LoadStage + event + L1/L0 handoff` 的固定成本不低。

或者：

\[ \textbf{B. 总数据搬运/布局效率} \]

特别是 `TB=false` 下宽 N 的 B panel 搬运效率不够好。

或者：

\[ \textbf{C. operand reuse 不足} \]

相同/相近 B panel 在多个 M macro 或不同 M shard 中不断重新装入，没有充分利用 Case12 的 wide-N 几何结构。

这三个方向现在值得依次区分。

------

# 4. 后面最值得考虑的实验和优化

| 优先级 | 方向                               | 具体做法                                     | 它回答什么                                 |
| ------ | ---------------------------------- | -------------------------------------------- | ------------------------------------------ |
| **P0** | **K1 granularity sweep**           | `K1=192 / 256 / 320`                         | 是 stage 数/setup 成本，还是总搬运量主导   |
| **P1** | **TB=false B-load specialization** | 针对实际 B 布局专门优化 Nd2Nz / panel load   | 单次 B feeding 本身是否低效                |
| **P2** | **macro aspect ratio**             | 如 `AM128×BN256 → AM256×BN128`               | 用更多 A traffic 换更少 B traffic 是否划算 |
| **P3** | **B reuse / B-stationary**         | 尝试让一个 B panel 服务多个 M macro          | 从根源消除重复 B load                      |
| **P4** | ring handoff                       | 减少 full-C macro 的 producer→AIV GM traffic | producer 优化后继续吃掉剩余几微秒          |
| 后置   | reduction / rowmax                 | 暂不做                                       | 当前证据不支持其作为主瓶颈                 |

其中我认为下一步最应该先做的是 **K1 sweep**。

当前：

\[ K=1536. \]

因此：

\[ K_1=192\Rightarrow8\text{ stages} \]\[ K_1=256\Rightarrow6\text{ stages} \]\[ K_1=320\Rightarrow5\text{ stages}. \]

这是一个非常漂亮的一变量实验。

如果表现明显随 stage 数变好，比如：

\[ 192>256>320 \]

而且差距明显，那么说明：

\[ \boxed{\text{stage granularity / feeding pipeline overhead 很重要}} \]

后面就继续研究 K1、double buffering、prefetch 和 event 节奏。

如果三者几乎一样，则说明：

\[ \boxed{\text{A/B sensitivity 主要来自实际 bytes / load efficiency}} \]

这时不要再调 K1，立即转向 TB=false 的 B load 和 reuse。

------

# 5. `AM/BN` 现在也值得重新看，但不要第一步就改

当前：

\[ AM=128,\qquad BN=256. \]

对于每个 macro，A panel 大致是：

\[ 128\times K \]

B panel 是：

\[ K\times256. \]

因此 B panel 本身就是 A 的约两倍规模。

而实验恰好又发现：

\[ \Delta_B>\Delta_A. \]

所以一个很自然的候选是保持 C macro 面积不变：

\[ 128\times256 \rightarrow 256\times128. \]

这样 C accumulator 元素数还是：

\[ 32768, \]

但理论上：

- B traffic 会减少；
- A traffic 会增加；
- M/N macro 数和 planner 会改变。

这和我们的敏感度结果方向一致，所以现在已经不是“随便换 tile”了，而是一个**有实验依据的 trade-off**。

不过它的副作用比 K1 大，所以应该放在 K1 sweep 后。

------

# 6. 更高上限的是 B-stationary，而不是继续微调参数

真正可能把 Case12 明显往 89 μs 拉的，未必只是 K1 或 tile size。

当前一个关键结构问题是：

> B 不依赖于 M，但不同 M macro / M shard 仍然会反复加载对应的 B panel。

对于 Case12：

\[ M\approx1.3K,\qquad N\approx4K\sim6K, \]

而：

\[ p_M\ge8,\quad p_N=2. \]

所以 B 数据天然有跨 M 复用机会。

一个更深层的 kernel 可能是：

\[ \boxed{\text{B-stationary / multi-M reuse}} \]

即把某个：

\[ B[k:k+\Delta k,\ n:n+\Delta n] \]

放进 L1 后，让它服务多个 M macro，而不是每算一个 `C[m,n]` macro 都重新装一次 B。

这个方向上限明显高于 final merge 优化。

但它可能要求：

- 多 C accumulator；
- 重排 K/M/N 循环；
- 新的 L0/L1 ownership；
- 重新设计 event pipeline。

所以我会把它作为 **第二阶段结构优化**，而不是下一次提交就做。

------

# 7. ring handoff 是明确的第二层成本

`RINGREAD_X2` 还有大约 4–5 μs 的明显敏感度。

当前路径实际上是：

\[ \text{MMAD/L0C} \rightarrow \text{Fixpipe} \rightarrow GM\ ring \rightarrow AIV\ UB \rightarrow rowmax. \]

producer 会把完整 macro 写入 ring，AIV 再读完整 half-macro 做 max。

所以等 A/B feeding 优化到一定程度后，可以考虑：

\[ \boxed{\text{能不能缩小 producer→consumer 的中间表示}} \]

而不是每次把整个 C macro 经 GM 走一遍。

但目前它的信号只有 B-load 的一小部分，因此不应该抢在 producer feeding 前面做。

------

# 8. 我建议现在正式冻结 Case12 的路线

可以把后续路线冻结成：

\[ \boxed{ \text{K1 sweep} \rightarrow \text{TB=false B-load specialization} \rightarrow \text{AM/BN geometry} \rightarrow \text{B reuse architecture} \rightarrow \text{ring handoff} } \]

而下面这些暂时冻结、不再继续投入：

\[ \text{r41 gate},\quad p_N,\quad rowmax,\quad partial,\quad merge,\quad SyncAll,\quad K\text{-tail}. \]

最关键的是，我们现在已经从早期的“Case12 为什么慢”收敛到了一个相当具体的工程问题：

\[ \boxed{ \textbf{Case12 的剩余性能缺口主要集中在 R30 producer 的 operand feeding； B-side feeding 是当前最强候选瓶颈。} } \]

接下来我认为**已经不用继续造诊断探针**。最合理的是开始做第一批真正的优化版本：`K1=192` 和 `K1=320`，以当前 256 为对照。这个结果会决定后面究竟继续优化 pipeline granularity，还是直接进入 B-load/B-reuse 重构。

​    

size能确定了吗

 



思考了 1m 51s

已分析

已分析

已分析

还不能把 **Case12 的完整 `(B,M,N,K)` 精确到唯一一组数**，但已经确定了相当多。

目前可以确定：

\[ \boxed{B=1,\quad K=1536,\quad TB=false} \]

并且 Case12 当前属于：

\[ 1280\le M<1536,\qquad4096\le N<6144. \]

由于 `bmms11r2::Eligible` 要求 `M,N` 都 16 对齐，而我们又已经实测 `R41_ALIGNED_PITCH=true`、`TB=false`；源码中的 pitch 条件这时变成 `N%64==0`。 因此现在至少可以进一步写成：

\[ \boxed{ M\in\{1280,1296,\ldots,1520\} } \]\[ \boxed{ N\in\{4096,4160,\ldots,6080\} } \]

所以 **K 已经精确，N 的粒度已经缩到 64，M 缩到 16，但 M/N 还没有唯一确定。**

另外，把你目前的 planner 探针结果：

\[ p_N=2,\quad p_M\ge8,\quad tasks=blocks=cores, \]

以及

\[ flatPeak=ExistingPeak \]

代回当前 `MakePlan()` 的实际逻辑后，候选实际上只剩下三类 planner 状态：

\[ \boxed{(cores,p_M,mTiles)=(20,10,10)} \]

或

\[ \boxed{(22,11,11)} \]

或

\[ \boxed{(24,12,12)}. \]

这是由源码中的 `mTiles=ceil(M/128)`、单 wave planner 和当前实测约束一起推出来的。 

这里尤其有一个很有用的结果：

- 如果实际 `pM=10`，那么由于 \(mTiles=10\) 且 \(M\ge1280\)，可直接推出  \[ \boxed{M=1280} \]
- `pM=11` 时，M 还可能是 1296–1408；
- `pM=12` 时，M 还可能是 1424–1520。

所以，**如果你的目的只是优化 Case12，现在其实已经不必知道精确 M/N 了**；现有信息足够做 K1、B-load、tile geometry 和 reuse 实验。

但如果你想把 Case12 的完整 size 最终钉死，也很容易：再做一组纯 metadata 强探针即可。由于 M 只有 16 个候选、N 只有 32 个候选，直接二分最多：

\[ \boxed{4\text{ 个 M probe}+5\text{ 个 N probe}=9\text{ 个}} \]

就能得到唯一的 `(M,N)`。

例如 M：

```
M_GE_1408
M_GE_1344
M_GE_1376
...
```

N：

```
N_GE_5120
N_GE_5632
N_GE_5888
...
```

每次继续用已经验证过的 `1.4ms` 强 timing encoder，HIT/NO 做二分即可。

所以结论是：

\[ \boxed{\textbf{现在已确定 }B=1,\ K=1536,\ TB=false;\ \textbf{但 M,N 尚未精确唯一确定。}} \]

如果只是为了继续优化，我建议**不要为了 shape 而 shape-probing**；如果你想把 Case12 档案彻底补齐，我可以直接给你生成一套 **9 个以内、自动二分 M/N 的 exact-size 探针包**。 
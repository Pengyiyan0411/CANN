# V9-D 原生完整 K 实验分支

状态：实现草案已完成；**未由 CANN 编译、未运行 NPU、未证明精度或性能提升**。只新增 `dense_fragment.asc`，不改 P01 原件。

## 交付与调用约定

将 fragment 插入 P01 的 `bmms83` 定义和 kernel wrappers 之后、原 `run_kernel` 之前。无外部 CATLASS include，无新增库或编译配置；使用当前默认 MIX 编译单元。

由主入口完成合法性解析后调用：

```cpp
bmms9d::TryLaunch(a,b,y,B,M,N,K,dtype,ta,tb,cores,stream)
```

参数顺序：`GM_ADDR a,b,y`；`int32_t B,M,N,K,dtype`；`bool ta,tb`；`int32_t cores`；`aclrtStream stream`。返回 true 表示已执行一次 launch，沿用 P01 的 stream 同步及 workspace 释放模式；false 表示未处理，交给原分支。TryLaunch 本身不访问输入数值，不做隐藏点识别。

8 个 kernel wrappers 完整覆盖 `half/bfloat16_t × NN/NT/TN/TT`。Host 函数为 `Eligible(M,N,K)`、`MakePlan(B,M,N,K,cores)`、`RingBytes/PartialBytes/WorkspaceBytes(plan)`。`Plan` 直接是 `bmms83::NativePlan` 的别名，便于无损复用原 consumer。

CPU 提取入口为 `bmms9d::StagedProducer<T,TA,TB>`，`Init(a,b,ring,plan,&pipe)` 后 `Process()`。`// BMMS9_CPU_EXTRACT_END` 位于所有 device 类和 namespace 结束之后；Entry 在 `BMMS9_CPU_TEST` 下排除。截断提取时需补全最外层 include guard 的 `#endif`。

## 第一版覆盖与计划

- M、N 均 16..8192 且为 16 的倍数。
- K 为 256..8192 且为 32 的倍数。更细 K 尾、非 16 对齐 M/N 留给 P01。
- B、输入规模、dtype、cores 在 wrapper 再检查；保留原 Tiny/Resident 分支，不接管它们。
- `pM=min(ceil(M/64),max(1,ceil(cores/B)))`；`pN=min(ceil(N/128),max(1,ceil(cores/(B*pM))))`；`tasks=B*pM*pN`；`blocks=min(cores,tasks)`。
- 与最初固定 pN=1 的草案相比，只在 B/M 划分不足时加入最少需要的 N 分片，防止 B1/M16/宽 N 全部交给一个组；不引入尚未校准的性能权重。D128/D64 使用完全相同的 Plan，仍仅比较 K stage 大小。
- 每个物理组按 `group,group+blocks,…` 执行任务，M tile 用整除边界连续切片。非整数波次、B>cores 都有真实循环，不假定每组恰好一个任务。
- 复用 `bmms83::SmallKConsumer`，因此 producer 严格使用其 **AM256 → BN512 → mo64 → no128** 顺序。AM/BN 此处仅决定消息/rowmax 的遍历顺序，**不表示**输入 A256 或 B512 常驻复用。

## 与此前设计的实际区别

这是**单层原生 K stage**，首个候选 `BMMS9D_K_BLOCK=128`，备选仅改为 64；不是已实现的 CATLASS `K1=256/K0=64` 双层流水，也没有引用 CATLASS BlockMmad。两种宏值由 static_assert 限定。

原始 P01 small-K Native 一次 MMAD 的 K 就是完整 K。新 producer 对同一个 TM64×TN128 输出块按 KB 连续加载、累加到同一 FP32 L0C；只在完整 K 结束后进行 Fixpipe。KB128 下末段 `kr` 可以为 32/64/96/128，所有 ND2NZ、LoadData、MMAD 都用真实 kr，不把未初始化 padding 参加点积。

固定同输出 tile 的 M/N 不变，所以每个 K stage 的 L0C 排列一致。下一输出 tile 重新读取输入；本版本不宣称跨全部 N 复用 A，也不宣称消除 C 的 GM 流量。

### 显式资源预算

| 资源 | KB128 默认 | KB64 对照 |
|---|---:|---:|
| L1 A 两槽：2×64×KB×2 | 32,768 B | 16,384 B |
| L1 B 两槽：2×KB×128×2 | 65,536 B | 32,768 B |
| L1 合计 | 98,304 B | 49,152 B |
| L0A 两槽 | 32,768 B | 16,384 B |
| L0B 两槽 | 65,536 B | 32,768 B |
| L0C 单槽：64×128×4 | 32,768 B | 32,768 B |
| 每组 GM C 两槽 | 65,536 B | 65,536 B |

KB128 的 L0B 正好达到 64 KiB，没有在该区域加入其他 buffer；这一显式用量与原 P01 TK128 的 L0B 相同。容量成立不代表未知编译器/API 隐含资源或真实性能已验证。

复用 consumer 的显式 UB 约为 `33,952 + 12*M` 字节：C queue16,384、group16,384、rows128、running1,024、output queue32，另 merged/tmp/sum 各4M。M8192 时 **132,256 B**，低于192 KiB；这里不虚构额外 API scratch 的已验证需求。

Workspace：ring=`blocks×2×64×128×4`；partial=`B×pN×M×4`。M%16，所有 row partial 和分段起点具备原 consumer 要求的 32B 对齐。pN>1 时保留 `[B,pN,M]` 的逐行 partial max，原 consumer 完成所有 N shard 的逐行 Max 后才 Sum(M)，不提前对 N shard 求 scalar sum。ring 和 partial 都是64B倍数；使用原 `SyncAll<true>()`，没有擅自发明额外 GM 同步协议。

## 地址和生命周期依据

输入地址均使用64位整数计算：

| 输入 | 非转置 | 转置 |
|---|---|---|
| A tile 起点 | `batch*M*K + m0*K + k0` | `batch*M*K + k0*M + m0` |
| B tile 起点 | `batch*K*N + k0*N + n0` | `batch*K*N + n0*K + k0` |

L1 每槽按最大 KB 分配，实际 ND2NZ 布局按 mr/nr/kr 紧凑存放。LoadData 的块步长同步采用真实 kr/mr/nr；KB128 的 kr96 尾不能错误沿用 KB128 的紧凑内部 stride。

每个 K 迭代：等本槽 MTE2→MTE1 ready；有下一段则等待其 L1 槽可复用并预取；等本 L0 槽上一条 MMAD 读完；执行 LoadData；在 MTE1 完成后归还 L1 槽；MMAD 完成后归还 L0 槽。输出 tile 结束只排空仍存在的 L1/L0 token，再发布 M→FIX。

single L0C 在下一个输出 tile 开始前等待上一 Fixpipe 的 `FIX_M`；该信用与 GM 两槽信用相互独立。GM 首两次使用跳过 FREE 等待，此后覆盖前等待对应槽 FREE；READY 在 PIPE_FIX 上发布。最后只等待已使用槽的最后一份 FREE 和最后一份 FIX_M。

两个消费者的 GM FREE 模式完全沿用 P01：每个 AIV 在本地 GM→UB queue 出队后于 PIPE_MTE2 返信用；mode0x2 的两 AIV 收齐语义仍需真实设备检验，离线 token 计数不能替代它。

第一版 M/N 16 对齐保证 mr 至少16且为16倍数，`vr=mr/2` 为8倍数；复用 consumer 的连续半行分工和32B partial copy成立。N tail 最小16，不读取 ring 未写的无效 N；原 consumer 将相应 UB lane 初始化为负无穷。

## 离线事实检查与设备门禁

建议父级 source 提取模型至少覆盖：

1. KB64/128、四布局、两 dtype；mr=16/32/48/64，nr=16/32/64/112/128；kr=32/64/96/128（受 KB 限制）。以坐标编码输入检查 ND2NZ→LoadData→MMAD 的每个元素来源。
2. K256/288/320/352/384/416/512/8192，对应2段、奇数段、各尾 kr 和多次槽回绕；验证 `cmatrixInitVal` 仅每个输出 tile 的第一段为 true。
3. M16/48/64/80/256/272、N16/112/128/144/512/528/8192、B1/3/64、cores1/2/20/64，检查 producer 和原 consumer 的 tile 序列完全相同，M/N 切片无漏写重复；尤其覆盖 B1/M16/宽N 的 pN>1 与多 batch、多 ns 的 partial 地址。
4. 每份 l1Ready/l1Free/l0Ready/l0Free/cReady/cFree 的 set/wait 数量与顺序；无token被重复设置或等待未发token。GM READY/FREE 独立按两消费者建模。
5. GM输入 guard、L1/L0 slot边界、ring stride、partial写范围及UB分配总量。

CPU 模型通过只说明模型下的地址和控制逻辑；不能验证真实 ND2NZ/Fixpipe 指令、事件流水、两 AIV barrier或设备精度。正式候选仍需比赛 CANN 编译、重复运行、输入不变与 guard、完整 FP64 oracle，再比较性能。

已知 FP32 C 强消减反例仍然存在；完整 K 后 Max/Sum 是必要语义约束，不是全域严格精度证明。半精度输入仍用 Cube 半精度乘法、FP32累加；未引入 FP16 C、近似 max、atomicAdd、跨核 Split-K 或 K shuffle。

## 技能适配

本轮补读 `catlass-operator-code-gen/SKILL.md`、`references/compile-options.md`、真实路径 `references/op_kernel/kernel-rules.md` 与 `custom-epilogue.md`。该 skill 原文针对 CATLASS/msopgen 工程；用户和主任务明确要求原生单文件、禁止外部 CATLASS 依赖，因此不运行 --genop、不要求修改 include path，不把本分支冒称该模板工程的完整交付。原有设计关于 ABI、dtype、布局、资源、workspace、生命周期和对照验收的约束继续使用。

# R26：保留 R25 Case5，按 packet 批量消费 Native 单 batch 输出

基于冻结的 R25_NATIVE_TARGETED，SHA256 为
`7defd06457ddb0e356cbf4cc8407f31cbb7c622acf6efd66070be212fa4eacb2`。
新回传两图的 Case5 为 6.60/6.45 μs，Case13 为 16.80/16.91 μs，Case14 为 13.84/13.63 μs。
用户没有再次写明文件名；按交付上下文归为 R25，原图和归属限制在独立结果目录保留。

R25 的 Case5 整 batch 归约路径冻结。当前工作只推进 13/14 的元数据域，等平台验证后再考虑其他点。

```cpp
// Only after the original earlier routes have declined, inside Native:
K == 128 && B == 1 && M > 32 && N > 32 && originalPlan.blocks > 1
```

Native 原入口还约束 M/N≥16、16 对齐，且排除 Tiny/Resident。
不使用测试点号、输入数据值、计时、历史输出或探针反馈作为运行时分派条件。
Case5 已定位 B>1，因此不命中新分支；原 `bmms25_small_*` 内核绑定、消费者、生产者、plan
和 workspace 原样保留。所有其他元数据不命中时仍执行 R25 原来的分派和内核。
未知测试点的完整元数据尚未公开，因此“目标域外源码不变”不能代替平台全15点的退化检查。

R25 的 DenseGatherConsumer 主要优化全局屏障后的分片汇总。前半程仍然逐小块进行
Alloc/EnQue/DeQue/Free、初始化整个 C 缓冲，并按每块下发 DMA。R26 将消费粒度与已有的
四块 packet 对齐。没有修改 Cube 形状、MMAD、Fixpipe、分核计划、输入读取量或 GM ring。

- 一次 READY 后，取得当前 packet 内最多四块的有效 mr/nr；顺序与原生产者的
  task → M stage → N panel → M tile → N tile 一致，允许跨 task、面板和 M stage。
- 连续的完整 N=128 列且有效 M 相同的块用一个 strided DataCopyPad 搬入。
  M 尾块如 mr=48/16 也可以合并；UB 固定每块占 32×128 float，其有效行数仍为 mr/2。
- 短 N 块按有效行列单独搬入，只对该块的有效行预填 -inf。不会读取 GM 未初始化的尾列或尾行。
- 每个 packet 一次 V→MTE2 等待保护 UB 复用，搬完后一次 MTE2→V 等待。
  两个 AIV 都在完整 packet 已进入私有 UB 后发 FREE，Cube 可复用 GM 槽位；归约继续读 UB。
- 保留原第一阶段 Max/WholeReduceMax 次序、partial 布局、单次 SyncAll，以及 R25 的
  N 分片树形 Max 和原 full-M ReduceSum。不是 Split-K，不引入低精度中间结果。

packet 暂存与屏障后的 merge/ReduceSum scratch 复用同一 UB 分配，阶段切换另有 V→MTE2 fence。
显式 UB 最大 148640 B；原生产者 L1/L0A/L0B/L0C 仍为 327680/32768/65536/65536 B。
这些是源码显式资源之和，不包含未知编译器额外开销。最坏内存检查范围 M≤8192、pN≤64。

这与历史 R05 的“延后行最大值规约”不同：R26 保留行规约顺序，改变 packet 搬运与释放时机。
它也不采用 R12 的第二次全局屏障或 R20 的宽 N Cube 路线。
完整列跳过冗余初始化曾被 R05 单独尝试过，因此本轮不把这一项单独宣称为已发现的新收益。

| CPU 逻辑工作示例（B1，K128） | R25 C DMA 调用 | R26 C DMA 调用 |
|---|---:|---:|
| M256，N1024，20组 | 64 | 32 |
| M256，N2048，3组 | 128 | 32 |

以上不是隐藏点真实 shape，也不是性能预测。两例的 MMAD/Fixpipe、C 字节量、READY/FREE 数量、
partial 读写和全局屏障数均不变。额外 packet cursor 的标量工作和实际流水重叠效果必须由平台判断。

验证使用提交文件中实际类/函数，继承原 Cube/内存模型并绑定源码 SHA256：

- R25/R26 各 318 次源码运行，含双 dtype、四 TA/TB、负数/零、ragged M/N、跨包复用；
  各70次隔离归并检查、194次重复输出核对。普通输出逐位一致，严格误差检查通过。
- 实际 host 函数 6276 次对照；6164 次目标域外完整记录与 R25 相同，其中80次为 Case5 元数据域。
  检查所有8个新 dtype/转置入口。故意删除 B==1 保护会被拒绝。
- 实际 packet cursor 对独立嵌套循环：1792 个计划、19322 个核组、341754 个 tile，
  覆盖93629个 packet 和最终1/2/3/4块。另核对32640组 UB 容量与 merge 边界。
- 错误 packet GM 步长、漏填短 N 列、尚未读完就 FREE 三项故障注入均被拒绝。
  CPU 模型不能模拟真实指令时延；手工事件顺序另按源码审阅。

没有本地 CANN 编译或 NPU 测试，没有证明完整极端数值域；旧 BF16 溢出、非有限中间值等限制未修复。
CPU 的 bitwise 相等也不保证设备编译后的逐位相等。平台必须先验收 15/15 Pass 再比较时间。

先提交 R26_DENSE_PACKET；对 13/14 观察可重复变化，同时核对 Case5 仍在原水平、其余点无稳定退化。
小幅单次变化不判定为收益。需要排除波动时用包内 CONTROL_R25 做相邻对照；失败或无收益回退 R25。
不要求新增 shape probes，不为这一轮申请额外算力。

API 使用保持 A2 已有接口。[DataCopyPad 官方说明](https://www.hiascend.com/doc_center/source/en/CANNCommunityEdition/900/API/ascendcopapi/atlasascendc_api_07_0265.html)
确认 float 和 A2 支持，GM stride 以字节计、UB stride 以32字节块计；本次最大单块16384字节、blockCount≤32。
沿用已通过提交的 mode2 双 AIV packet credits；没有换用新架构专属的同步模式。

复现顺序见提交包 README；各检查报告保存源文件 hash 和验证边界。

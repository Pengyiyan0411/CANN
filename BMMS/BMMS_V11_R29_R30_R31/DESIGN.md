# R29–R31 设计与验证边界

## 证据与目标

冻结基线：R25_NATIVE_TARGETED，SHA256 `7defd06457ddb0e356cbf4cc8407f31cbb7c622acf6efd66070be212fa4eacb2`。
三个候选仅追加一个独立命名空间、八个 dtype/layout 绑定和一处受元数据约束的分派调用。删除新增片段和调用后，除版本标题外逐字恢复 R25。

已知：Case5 为 K128、M/N各16或32、B>1；Case13/14 为 K128、B1、M/N>32；Case7 位于原 R03，M<128、N<256、K256..480/32、B<cores。Case15 的长 K Split-K 已稳定改善，R28 的进一步改动未显示收益。Case6 的路线未知；不对未定位点编造形状。

本轮改变输入加载和 Cube 指令粒度。先独立验收，不把互不相干的策略变更合成一个无法归因的成绩。

## R29：整个短 K 驻留 L1

原 R03 输出块为64×128，每 K128 片段分别做 A/B 的 GM→L1 ND2NZ。目标 K 在256..480，每块有2–4组加载和 L1 交接。

新实现将该输出块的整个 K 一次装入单份 L1。L0仍双缓冲 K128，MMAD 的 K顺序、分块、初始化及最终 Fixpipe 都保持原式。四种 TA/TB 使用完整 K 的 NZ 源跨度，并用 k0 定位切片；尾片仍为32的整数倍。L1 在所有切片读完前保持不可覆盖，MTE1_MTE2 事件完成后才允许下一输出块复用。

原 planner、64×128输出块、GM环、消费端和全局归约不改。只在原 R03 合法且 M<128、N<256、K<512、B<cores 时进入，仍继承 dtype、对齐、范围、Tiny/Resident 排除。

模型例 `(B,M,N,K,cores)=(1,112,240,480,4)`：ND2NZ调用32→8，MMAD仍16次，输入字节数和全部 C 输出字节数相同。这是逻辑工作量，不能解释成实测加速倍数。一次更大的输入加载也可能延后首个 MMAD。

## R30：Native 的128×128块

仅 K128、B1、M≥128、N>32、原 Native blocks>1。M≥128是策略约束，尚未由探针证明13/14都满足。

复用原固定 K生产端的布局转换和同步协议，将TM64改为128。AM256、BN512不变；GM包从4个64×128块改为2个128×128块，包字节数不变。两个 L0C 槽和独立 GM包 credit 均保留。消费端按新 TM 读取上下半块，每个 AIV 最多64行。最终仍先合并 N 分片的行最大值，再按原全 M ReduceSum 输出。

按新 tile 几何运行原成本公式，pM/pN 可能变化。所有输出分片无空片、无遗漏、无重复；分派检查覆盖 1,735 个分片。增大 tile 可能降低小形状的空间并行，因此必须验收实际延迟。示例 `(1,384,528,128,8)`：MMAD/Fixpipe30→15，GM输入字节数不变；这不能直接推断延迟减半。

原 DenseGatherConsumer 的合并临时区上限从16384缩到8192个float，防止 TM翻倍使UB超出预算。M≤8192、pN≤64范围的最坏 UB 为165152字节。

## R31：Macro 的K128计算块

保持原 MacroEligible 和所有 Classify 排除条件、MakePlan、128×256宏块、GM环、RowMaxConsumer、最终归约。

K1仍256并保留双份 L1。K0从64改128后，L0改为单槽，下一次 LoadData 必须等待这一槽的 M_MTE1 credit。若直接保留双份 L0B，会占131072字节，超出原64KiB预算。新实现将 L0A/B 总占用维持32768/65536字节；四个输出小块共享的 L0C 仍131072字节。

大多数整 K 块 MMAD次数减半；尾片数按ceil(K/128)计算。如K288，每输出小块从5次变3次。输入字节数、Fixpipe数及GM发布协议保持原样。代价是失去原 L0 ping-pong 的预取重叠；是否值得由平台计时决定。K粒度变化也需要平台精度验收，CPU串行FMA逐位一致并不证明硬件归约等价。

## 每个 AIC 的静态资源预算（字节）

| 候选 | L1 A+B | L0A | L0B | L0C |
|---|---:|---:|---:|---:|
| R29 | 196608 | 32768 | 65536 | 32768 |
| R30 | 327680 | 65536 | 65536 | 131072 |
| R31 | 393216 | 32768 | 65536 | 131072 |

沿用既有A2源码模型的预算：L1≤512KiB、L0A/B各≤64KiB、L0C≤128KiB、UB≤192KiB。没有声称探测了平台型号或获取了新的硬件报告。

## API 核对

实现沿用基线已经使用的 ND2NZ、LoadData2D、MMAD、Fixpipe 和事件 API，不新增架构专属接口。R29 的源跨度以16×16半精度分形计算，并保持512B的L0输入对齐；来源核对见官方 [LoadData 2D](https://www.hiascend.com/document/detail/en/CANNCommunityEdition/910/API/ascendcopapi/docs/en/api/SIMD-API/basic_api/cube_compute_ISASI/cube_compute_load/Load2D.md) 与 [矩阵基本编程示例](https://asc.gitcode.com/guide/operator_practice/simd_operator_impl/matrix_basic_api/coupled_mode.html)。

MMAD仍half/bfloat16输入、float累加，A为Zz、B为Zn、C为Nz。小输出累加时保留原PIPE_M依赖，L0C重用依赖独立于GM环credit。对齐和格式核对见官方 [Mmad](https://asc.gitcode.com/api/SIMD-API/basic_api/cube_compute_ISASI/mmad_compute/Mmad.html)。R30的GM目的行距仍TN128，源跨度为实际mr；参考 [Fixpipe](https://www.hiascend.com/doc_center/source/en/CANNCommunityEdition/900/API/ascendcopapi/atlasascendc_api_07_0251.html)。文档核对不替代目标CANN编译。

## 已执行验证

使用 AscendC performance-optim 工作流，按无本地CANN/NPU的既有约束执行离线验证。继承模型生成器和每个头文件先与 R25 CHECKS 中的SHA256匹配，新增提取代码直接来自交付的`.asc`。

R25与候选集合各216次执行：R29范围80、R30范围68、R31范围68；每版108次反序启动复核。两种输入类型、全部四种转置、K尾片、M/N尾块、多任务、负数、零和普通随机数均覆盖。严格参考条件为绝对误差与相对误差均小于1e-4，模型最大绝对误差7.62939453125e-6，全部输出与R25逐位一致。

所有有效输出写读恰好一次，部分行结果恰好一次，GM环发布/释放守恒，局部事件无遗留、输入不变、资源预算通过。80,598次实际主机分派比较，其中74,002次非目标完整启动记录不变。Case5保护384次、Split-K保护702次。

故障对照：R29删掉转置A的K起点导致错误结果；R30提前发布包触发未完成包访问；R31错误使用第二L0槽触发无credit等待；R30删除B1条件触发非目标分派变化。四种错误均被检出。

未执行：CANN编译、NPU精度、NPU性能、全输入域数值证明。模型顺序执行单条设备指令，不能完全模拟硬件流水重叠、编译器分配或所有异步时序。R25仍是性能基线；三版需平台15/15 Pass以及相邻对照后才能晋升。

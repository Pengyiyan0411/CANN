# R27：撤回 R26 升级推荐，隔离验证 Native dense 的 Cube 同步

当前任务只处理13/14，并保留5的 R25 特化。没有本地 CANN/NPU 环境，R27 是待平台验证候选。

## 重新确认结果和结论

| Case | R25 第1次 μs | R25 第2次 μs | 本次 R26 μs | 本次平台最优列 μs |
|---|---:|---:|---:|---:|
| 5 | 6.60 | 6.45 | 6.86 | 1.89 |
| 13 | 16.80 | 16.91 | 17.26 | 5.19 |
| 14 | 13.84 | 13.63 | 13.77 | 5.40 |
| 15 | 15.30 | 15.03 | 15.43 | 4.05 |

截图按交付上下文归为 R26；用户没有重述文件名，无法校验平台源码 hash。
本次15/15 Pass，误差栏0.00%，但13/14没有可见收益；5也高于原两次观测，不能直接用“波动”解释掉。
保留 R25 为工作基线，R26不合入。原图和完整15点读数在 `V11_results/2026-09-27_r26_observed/`。
最优列不是固定标杆，不能混用不同日期的值推断本次绝对性能改进。

1. **不是先认定没有命中。** N01/N02没有压力响应、N05强响应，支持13/14为 Native、K128、B1；
   N03/N04无响应的解释依赖已标定的 one-group 压力信号。基于这些证据，M/N>32、blocks>1，
   因而进入R26目标分支。真实host源码对照也支持该分派；仍保留截图归属和隐藏元数据的证据边界。
2. **DMA调用减少不等于实际字节减少。** R26没有降低 C 有效字节、MMAD/Fixpipe次数、跨核credits和屏障次数。
   新增游标和包处理也有代价。因此此次无收益不能唯一证明“Cube算力受限”“内存受限”或“归约已最优”。
3. **M_FIX不是整条流水的Scalar屏障。** 它让FIX等待对应MMAD；双缓冲已经允许不同块重叠。
   正确的候选假说是：解除同一块的整块等待是否有收益。不是“原先没有流水，新版才有”。

## 源码改动范围

基线：`BMMS_V11_R25/R25_NATIVE_TARGETED.asc`，SHA256
`7defd06457ddb0e356cbf4cc8407f31cbb7c622acf6efd66070be212fa4eacb2`。

R27在原Native路由已选中后才增加一个分支：

```cpp
p.K == 128 && p.B == 1 && p.M > 32 && p.N > 32 && p.blocks > 1
```

只使用运行时输入元数据、原计划，未使用测试点号、输入值、历史输出、计时结果或探针结果作运行时判断。
13/14是该域的已知目标，其他未定位测试点是否共享同一域仍须平台检查。
Case5已定位为B>1，不能进入R27；原R25小batch消费者、生产者、8个入口、plan、workspace全部逐字保留。
R23 Split-K及所有其他原路由也保留。可删除新增片段和hook，逐字恢复R25（标题除外）。

新增8个内核覆盖FP16/BF16及4种TA/TB。AIV直接使用原 `bmms25::DenseGatherConsumer`，
没有携带R26的packet消费者。AIC仅复制原 `SmallKProducer` 并改MMAD/FIX握手：

- 一块有且仅有一次完整K128 MMAD，`cmatrixInitVal=true`；`q.unitFlag=3`。
- 对应Fixpipe仍完整搬出同一mr×nr浮点结果，`srcStride=mr`，`ndNum=1`；`f.unitFlag=3`。
- 删除每块M_FIX的Set/Wait和两枚事件分配。保留M_MTE1、FIX_M及原双L0C槽位复用保护。
- `(mr/16)*(nr/16)<10`的小块补PIPE_M依赖；这类块不会声称获得完整的细粒度重叠。
- 为现有NZ→ND搬出设置 `SetMMRowMajor()`；最终M/FIX工作排空后恢复 `SetMMColumnMajor()`。

没有改变K归约、MMAD形状、输入装载、精度、C字节数、packet顺序、最终Max/ReduceSum。
没有扩大Guard、加全局同步、改变核组数或 workspace，也没有引入原子累加。

## 同步与尾块审阅

| 依赖 | R27处理 | 理由 |
|---|---|---|
| GM→L1可读 | 原MTE2_MTE1 | 不改变输入加载 |
| L1复用 | 原MTE1_MTE2 | 不覆盖尚被LoadData读取的面板 |
| L0A/B可读 | 原MTE1_M | 输入完成后才能MMAD |
| L0A/B复用 | 原M_MTE1 | 保留MMAD对旧操作数的占用 |
| 本块L0C→FIX | 成对UnitFlag=3 | 唯一被替换的块级生产/消费同步 |
| L0C槽位复用 | 仍保留FIX_M | 同一槽位下次MMAD前等待原搬出；不同时试探删掉此保护 |
| GM槽位复用 | 原双AIV FREE | UnitFlag不保护GM；绝不代替这条跨核依赖 |
| 发布packet | 原PIPE_FIX READY | 完成GM输出后才允许AIV读取 |
| 全局归约 | 原一次SyncAll | partial合并与R25完全一致 |

mr/nr始终为16的倍数，末块有效尺寸被MMAD和Fixpipe共同使用。
每次MMAD计算的整个矩阵都被对应Fixpipe搬出，避免未读L0C单元残留。
slot0/1间隔固定64×128×4字节，矩阵最大占满各自槽位，不重叠。
不在L0C上分次累加K、不做部分Fixpipe、更不以清空标志来掩盖未消费数据。

保留的FIX_M依赖没有形成循环：对槽位s的复用等待位于完成该槽位上一轮MMAD之后，
而被等待的Fixpipe只依赖上一轮MMAD和该packet的FREE；消费者不等待下一轮MMAD才释放旧packet。
结束时先发布不足4块的末包，再等待最后FREE和所有本地事件，沿用R25顺序。
这属于源码依赖审阅，不是设备时序仿真。

## 资源和验证

显式buffer分配与R25相同。AIC L1/L0A/L0B/L0C为327680/32768/65536/65536字节。
原消费者在既有M≤8192、pN≤64容量检查域内UB上界165024字节；本轮实际CPU样本峰值131104字节。
这些不包含未知编译器额外开销，也不把原检查域扩大为所有可能输入的资源证明。

- R25/R27各318次实际生产/消费源码模型运行、70次隔离归并、194次重复核对；
  含双dtype、四布局、正负/零、尾块、多个packet、多任务、反向线程启动。
  输出逐位一致，严格绝对且相对误差均小于1e-4，普通样本最大绝对误差1.52587890625e-5。
- 6276次真实host函数对照：6164个目标域外完整调用记录与R25一致，其中80次属Case5元数据；
  112次目标域只切换到新内核，原计划和分配不变。所有8个新增绑定覆盖。
- 新增独立整块所有权契约，检查UnitFlag成对、完整搬出、L0C复用、排空与方向恢复。
  单边MMAD标志、单边FIX标志、部分搬出、漏小块依赖4项故障注入均拒绝；扩宽host Guard也拒绝。
  契约不模拟硬件单元标志的粒度、延迟、缓存可见性或编译器行为。

实际源码模型中的示例：B1/M256/N1024/K128/20核组计划使用16组、32个tile。
R25有32次M_FIX等待，R27为0、32对UnitFlag；64次C DMA、输入/C字节量、MMAD/Fixpipe数量、
16次READY、32次FREE、一次全局屏障都保持不变。该shape是检查样本，不是隐藏13/14的已知shape。
这个计数证明改动确实发生，不能换算成微秒收益。

本地没有CANN编译或NPU测试。CPU浮点模型不能证明硬件逐位相等或所有极端数值正确性；
原BF16溢出/非有限中间结果等限制并未由这次同步改动解决。

## 验收和停止条件

只提交 `R27_DENSE_UNITFLAG.asc` 一个候选；`CONTROL_R25.asc` 是原字节对照。
先检查15/15，再看13/14是否有可重复下降，同时检查5及其余点。
若仍只有此前的小幅起伏，就退回R25，不把新版本当作升级，也不继续扩大这套优化的适用域。
新旧源码相同不能作为硬件性能无退化的证明；必要时用包内对照做相邻提交。
本轮不需要继续旧A–C/N探针，不推进其他测试点，不额外申请算力。

## 官方API依据

- [Mmad及A2的unitFlag支持](https://www.hiascend.com/doc_center/source/zh/CANNCommunityEdition/910beta2/API/ascendcopapi/atlasascendc_api_07_0249.html)
- [FixpipeParamsV220及unitFlag](https://www.hiascend.com/doc_center/source/en/CANNCommunityEdition/900/API/ascendcopapi/atlasascendc_api_07_0251.html)
- [UnitFlag特性、完整搬出和小块约束](https://asc.gitcode.com/api/SIMD-API/basic_api/cube_compute_ISASI/mmad_compute_key_features/UnitFlag.html)
- [CANN9.0 SetMMRowMajor，A2支持](https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/900beta1/API/ascendcopapi/atlasascendc_api_07_0260.html)
- [官方性能策略适用条件](https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/83RC1/opdevg/ascendcbestP/atlas_ascendc_best_practices_10_10006.html)

UnitFlag的作用是细化MMAD/Fixpipe之间的同步，不能加速单条指令本身。
只有相关等待在端到端时间中占有足够比例才可能有明显收益；本轮没有profiler证据确认这一比例。

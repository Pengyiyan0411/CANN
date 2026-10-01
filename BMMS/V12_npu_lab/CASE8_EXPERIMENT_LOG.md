# Case8 设备实验记录

父版本：`BMMS_V12/v12_baseline_r12.asc`。用户已确认该版 Case15 稳定约 11.5 μs，其他点基本无影响。Case8 精确隐藏形状仍未知，本轮样本均为符合原 R43 元数据域的合成输入，不能称为比赛原题输入。

## 测量约定

- Ascend910_9362、逻辑设备0、20 Cube cores，CANN 9.0.0，dav-2201。
- 一次只运行一个 NPU 性能任务，编译与性能测量分开。
- CPU FP64 参考：先把输入量化至实际 FP16/BF16，完整 K 求和，再 N max，再 M sum。
- 设备事件计时：预分配输入与 workspace，同进程交替 A/B 和 B/A，每个窗口64次真实 kernel。含流执行与提交间隙，不含公共入口分配/同步，非 Judge 计时合同。
- 首轮性能筛选为3组尺寸、各4转置的12个 FP16 输入；正确性首轮为这3组的全部8种 dtype/layout，共24例，每例3次。

## 阶段定位

单独 pack、已经 pack 后的计算、完整路径分别测试。pack 输出逐字节对照独立物理矩阵补零；计算对照 FP64。phase 0/1/2 分别为 full/pack/compute，记录在 `results/c8_phases.jsonl`。

12个样本：pack 约12.4–15.2 μs，full 相比 compute 增加约5.8–9.3 μs。阶段时长并不严格可加，不能把整个 pack-only 时长当作可省去的端到端时间。

例：M1041/N1105/K1064，FP16 NN，原计划 pM4/pN5/20blocks。full52.865、pack12.485、compute46.926 μs。轻量 PipeUtilization 中，原版 AIC MTE2 活跃时间约24.629 μs，MAC约10.041 μs；管线并行，不能直接相加或据此算严格瓶颈占比。

## 第一轮：r13，整列 NZ 条带整理

原始输入每次读16列，写成 `[physical_column/16, padded_physical_row,16]`，Cube 用整段 DMA 读入已有 L1 NZ 格式。原计算与计划不变。

24/24例通过。12点筛选耗时缩短中位数 **-26.10%**，即变慢26.10%；最大退化54.13%。不提交。

补充计数器在上面 NN 样本显示：AIC MTE2 从24.629降到7.341 μs，AIV MTE2 升到23.287 μs。说明后端读法有效，但逐16列整理让前端成为新的开销来源。该证据支持再修改整理粒度，而不是沿用失败版本。

## 第二轮：r14，128×128 宏块

双 L1 K512、双 L0 K128、完整宏块 MMAD、按单宏块分配任务。资源为 L1 512KiB、L0A/B各64KiB、L0C128KiB；没有重复旧 R31 的单 L0B 方案。

24/24例通过。12点缩短中位数 **-8.76%**，布局间差异很大，最大退化31.60%。不提交。事件测试程序初版 workspace 分配漏计新 partial 大小，在运行该事件程序前已停止自动任务、修正并重新编译；所有归档 r14 性能数据来自修正后的程序。公共提交源码的 workspace 计算一直按新计划分配。

## 第三轮：r15，直接从原输入读入 L1

保留原宏块与计划。读取真实物理 stride，在 L1 边界块显式补零；省去 A/B 整份整理及 pack 屏障。

24/24例通过。12点缩短中位数 **-54.19%**，全部变慢；最大退化141.99%。说明省掉前处理并不足以抵消这种直接读取方式的代价。没有对失败版本继续扩展性能测试或推荐提交。

## r16：NZ 方向的第二次实现

保留 r13 的 Cube 输入排布，只把前端改为最多256行×128列一次读取，再在 UB→GM 阶段写8条 C0 条带。每个 job 的目标区域不重叠；双槽直到全部条带写完才释放。其余 R12 源码逐字节保留。

24/24例通过，12点耗时中位增加138.79%，最大退化159.55%，淘汰。代表NN样本AIV MTE2约10.744 μs，但MTE3达到57.991 μs；问题转移到大量跨距小写入，不能只看Cube端改进。

## r17：UB内重排后批量写GM

仍按256×128读取，但将原128KiB pack UB拆成64KiB ND区与64KiB NZ区，用UB→UB DataCopy重排32B块，再整段写GM。Cube端与r13/r16相同。

首轮12例收益强烈依赖尺寸/转置；扩展40例耗时中位缩短约14.02%，但最大退化约19.21%。该40例用于选分派规则，不能再称为规则的独立验证。r17全域版本不提交。

## r18：保留实测有利的stride/layout分支

在原R43 guard内，仅当 `(TA && Mp%64!=0) || ((TB?Kp:Np)%64!=0)` 时采用NZ。其余调用在分配/launch前回退原R43。该条件是经验性能策略，不是API约束；宏块、planner和归约保留。

冻结规则后生成新的40例：26例命中新路径，14例回退。首测整体耗时中位缩短15.30%，独立复测15.49%；新路径26例中位缩短27.03%/26.67%。初始样本A/A范围约-0.133%～+0.099%。详细精度、控制路径复测和sanitizer结果见 [最终报告](results/case8_20260928/REPORT.md)。

sanitizer初次普通构建的racecheck/initcheck明确被跳过，不算通过；另建带`--cce-enable-sanitizer`的同源检测程序重测，性能数据不使用插桩程序。

## r19：显式归约尾部掩码

有效插桩后发现r12/r18最终`Max(merged,merged,tmp,p.M)`均被memcheck报64条UB读写告警；该段消费者源码完全相同。r19保留r18的分派和搬运，仅将新模块中的这个Max改为完整64元素重复＋单独尾部掩码。

同2例的插桩memcheck降为0条ERROR，racecheck/initcheck仍有保留计算链的同类告警，未宣称全面通过。258组×3次精度通过。原40例复测耗时中位缩短15.03%/14.83%，保留了主要收益。最终交付以r19为唯一比赛候选，r18留作研究对照。详细结果见最终REPORT.md。

## API 依据

NZ 数据布局按官方 [CANN9.0 ND2NZ](https://www.hiascend.com/doc_center/source/en/CANNCommunityEdition/900/API/ascendcopapi/atlasascendc_api_07_00127.html) 的 C0=32B 和 stride 单位，以及设备安装头文件实现核对。它只为物理列末尾的 C0 补零，缺失整行仍须显式初始化。

r15 的 L1 初始化依据 [InitConstValue](https://www.hiascend.com/document/detail/zh/canncommercial/81RC1/apiref/ascendcopapi/atlasascendc_api_07_0237.html) 的 A1/B1 32B block 单位，另核对实际 CANN9.0 `kernel_operator_mm_base_impl.h`；该版本虽精度通过，性能已淘汰。

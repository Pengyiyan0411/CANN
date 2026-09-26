# R17 / R18 / R19：按用户计划，以R14为父版的三个独立实验

## 执行边界与归因

本轮依据用户指定的[技术审计计划原文](INPUT_PLAN.md)第6、10节。采用R14作为后续开发基线，
这是本次计划选择，不是新的复测结论。R14观测37.259712分、父版R11观测36.937232分，
差异仍未排除测评波动。第11点约135→100μs的主要改善来自R11，不能重复归功于R14。

本轮不重新命名冻结的R15/R16，不合并它们，也不宣称它们已有平台反馈。
将两项完全相同的覆盖修改分别迁移到R14，编号R17/R18；新的A驻留实验独立编号R19。
控制文件R14_CONTROL与已交付R14的SHA256一致。所有候选保持原入口ABI和官方工程结构。

| 候选 | 仅相对R14改变 | 保持的部分 |
|---|---|---|
| R17_R14_K32_GAPS | K=96/160/192/224的手写路径准入 | R14规划器、全部device代码 |
| R18_R14_K16_TAILS | K=48..8176且K%32==16的准入 | R14规划器、全部device代码 |
| R19_R14_A_RESIDENT | K256/512时，完整A跨多个N宏块驻留L1 | R14准入、网格、MMAD序列、输出协议、消费者 |

R17/R18仍要求M/N均16对齐，保留Tiny/Resident和K32/64/128专用路径。
没有放宽到K%8==0或M/N非16对齐，未加入量化、拆K、半宏块输出或AIV预取。
后几项是计划中的后续分支，不与首轮三个实验混合提交。

## R19的启用条件

先通过R14原有宏块Eligible，使用原样R14 MakePlan，再检查：

```cpp
(p.K == 256 || p.K == 512) && p.pN > 0 && p.nTiles >= 2 * p.pN
```

即每个任务的N分片至少包含两个宏块；一组可能承接多个任务，每个任务都必须满足复用条件。
若分片长度混合为1/2块，整个launch保留旧生产者。这个首版边界比“只要某组能复用就启用”
更窄，避免在同一新kernel中再引入两套A生命周期。它不是性能阈值或最优形状定律。
资格之外保留R14原生产者；residual/native/向量族保持原样。

R19新增16个入口实例：两种K×两种dtype×四种布局，每个入口只实例化一个固定RK生产者。
原8个宏块入口和原生产者保留。这样每个设备入口只申请一套对应缓冲，不在同一kernel
入口中并置三个生产者的InitBuffer分支。CANN的实际代码生成和编译耗时仍待平台确认。

## 数据流和地址

每个任务按原次序遍历M宏块、N宏块。进入一个M宏块时，先将完整A[ar,RK]搬到L1一次；
完成这个M块的全部N扫描后，才允许下一个M块或batch覆盖A。B继续沿K1=256双缓冲。
L0仍按K0=64顺序加载，依次计算四个64×128微块；完整K之后才Fixpipe和Max。

完整A的NZ存储使用实际ar和完整RK。设k=kBase+kk，i是当前64行微块内的16行编号：

```text
TA=false: A1 offset = (k/16)*ar*16 + (mo+i*16)*16
TA=true : A1 offset = (mo/16+i)*RK*16 + k*16
```

TA=true的stride使用完整RK；K512的第二个K1面板必须包含kBase=256。
B的地址、转置、L0槽布局均沿用原代码。输入GM行步长仍来自原始M/K/N，不把片上布局
步长误用于GM。M/N尾块继续使用原ar/br/mr/nr，未读取虚构的输入padding。

[官方ND2NZ参数说明](https://www.hiascend.com/doc_center/source/en/CANNCommunityEdition/900/API/ascendcopapi/atlasascendc_api_07_00127.html)
用于核对srcDValue与dstNzC0Stride的单位及含义。实际寻址另由源码CPU布局模型核对。
模板的完整K=256/512均由公开shape决定，不读取输入内容作路径选择。

## 生命周期和资源

原l1Ready/l1Free只管理B面板；新增aReady/aFree分别管理完整A的加载完成和扫描结束。
A加载后使用MTE2_MTE1同步；全部N扫描结束后用MTE1_MTE2保护覆盖。各B面板仍在最后
一次L0读取后释放，l0Ready/l0Free及FIX_M/M_FIX不变。

两类事件各从2个持有ID增加到3个，其余事件数量不变；申请与释放成对。
[官方AllocEventID说明](https://www.hiascend.com/doc_center/source/en/canncommercial/800/apiref/ascendcopapi/atlasascendc_api_07_0114.html)
和[ReleaseEventID说明](https://www.hiascend.com/doc_center/source/en/canncommercial/800/apiref/ascendcopapi/atlasascendc_api_07_0115.html)
用于检查占用和配对原则。CPU模型检测信用不平衡，不模拟真实流水可见性；实际A2编译仍需平台验证。
原每个Macro收尾也会等待B的MTE1_MTE2，新增A结束事件使生命周期边界明确，不把它宣称为
唯一的覆盖保护或新的并行收益。

| 每AIC显式申请 | R14 | R19 K256 | R19 K512 |
|---|---:|---:|---:|
| A L1 | 128 KiB | 64 KiB | 128 KiB |
| B L1 | 256 KiB | 256 KiB | 256 KiB |
| L1合计 | 384 KiB | 320 KiB | 384 KiB |
| L0A / L0B / L0C | 32 / 64 / 128 KiB | 相同 | 相同 |

每组ring、partial布局和AIV缓冲不变。未把GM ring的两个槽误称为L0C双缓冲。
完整C仍经FP32 GM ring中转，R19只降低A的GM→L1逻辑读取；B、L1→L0和C流量不变。

对同一实际Plan，设mt=ceil(M/128)、nt=ceil(N/256)：

```text
原A读取 = 2*B*M*K*nt
驻留A读取 = 2*B*M*K*pN
B读取（不变） = 2*B*N*K*mt
```

收益随每个N分片长度变化，也受缓存、计算瓶颈、额外A同步和编译器实现影响。
GM逻辑字节不是实际HBM事务，节省比例也不是耗时提升比例；不承诺翻倍。

## 本轮验证

- 独立提取实际host选择分支，将launch表达式替换为记录目标名字，核对29568组选择和16个kernel模板绑定。
- R17/R18在实际R14计划下重跑原用例和K新域，检查Resident/Tiny保护和K尾地址；与旧R15/R16相同输入结果对照。
- R14/R19使用相同新增用例，覆盖两K、两dtype、四布局、M/N尾块、多batch、多任务和多N分片；普通输出逐位比较。
- 从实际ND2NZ/LoadData/Mmad/Fixpipe调用统计A/B字节、次数、L0字节、计算次数、C流量和ring信用，独立公式核对。
- 单次L1峰值另行统计，不拿整个测试历史的最高值代替某个K256实例的申请。
- 故障注入：错误使用K1作转置A步长、遗漏kBase、未刷新后续M块A；均须被拒绝才能打包。

精度样本使用可精确表示的有界输入，标杆为实际输入的FP64计算。原有3项极端数值限制
继续保留；CPU通过不能扩展为任意BF16输入的精度证明。最终数量、源码哈希和实际结果
以[CHECKS.json](CHECKS.json)为准。本轮无本地CANN编译、NPU正确性或时延数据。

## 提交顺序和后续

按计划依次提交R17、R18、R19，各自都配R14控制；出现明显变化后做R14→候选→R14复核。
不要先合并三个候选。R17/R18无变化不能证明隐藏点未命中，R19无变化也不能证明A重读
没有成本；应记录目标域和可复核收益，再决定是否扩大域或进入输出生命周期实验。
下一阶段半宏块双L0C与AIV预取继续独立，不通过故意失败猜隐藏测试形状。

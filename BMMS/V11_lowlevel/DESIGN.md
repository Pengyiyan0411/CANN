# R05 / R06：归约复用与整宏块Cube指令

本轮平台截图按唯一前序候选归属R04，15/15 Pass，同本轮T复算34.496451分。
用户只写“SOTA”而未再次写文件名，因此证据记录注明上下文归属，不称平台源hash已验证。
R04保住R02点9–12及R03点7/15的收益，冻结为当前保底版本。
本轮继续采用已装载AscendC性能优化技能的源码排查、保存基线、独立修改和验证流程，
按用户授权以CPU检查及平台提交代替目前不可执行的本地设备阶段。

## 排查与取舍

| 发现 | 源码事实 | 本轮处理 |
|---|---|---|
| AIV重复行归约 | 每个N面板重新初始化acc、归约行最大值，再与running max合并 | R05将128列lane max保留到N扫描结束 |
| 完整C块冗余清填 | nr=128时DMA覆盖所有读取元素，仍先Duplicate(-inf)和手工V_MTE2 | R05仅尾N保留清填，TQue复用依赖保留 |
| 宏块MMAD被拆开 | 同一K0片的128×256宏块调用四次64×128 MMAD | R06改变L0排布，使用整宏块MMAD |
| MTE1小循环 | A按M片逐行、B按两个N微块分别LoadData | R06选择较短循环轴和dstGap，合并B宽度 |
| 新API硬件适用性 | Load2D V2只支持更新代产品，A2不支持 | 使用A2已有LoadData2DParams、Mmad和Fixpipe |
| GM输出握手 | R02已做到每宏块一次READY、两槽复用 | 本轮保持协议及flag编号 |
| 其他优化空间 | 点8/13仍明显慢，但无真实shape和profiler | 不按点号改路由，也不声称已定位其kernel |

继续保留FP32全K累加、完整K之后max N再sum M；不做FP16 C、不使用输入值特判。
两版均由R04独立派生。R06不含R05，R05不含R06；先判断单项收益再组合。

## R05_DEFERRED_MAX

对一行的完整K结果记为`C[n]`，令lane号`l=n mod 128`。可按以下恒等式归约：

`max_n C[n] = max_l (max_{n mod 128 = l} C[n])`。

每个AIV给自己负责的每一行保留128个FP32 lane最大值。宏块的mo遍历交错出现，
所以不同M微块必须有独立acc区域，偏移为`(mo/2)*TN`；不能只延长旧单acc的寿命。
等当前M面板的全部N扫描完毕，才做一次破坏性的lane fold和WholeReduceMax，
直接写入runningBuf中的对应行，再沿用原来的partial和最终sum。

只重排Max操作，不改变任何点积或M方向求和次序。该等式对无NaN的计算结果成立；
既有BF16中间溢出限制未宣称修复，也不将特殊浮点值归约语义等同于完整数值域证明。

同时，完整128列C块跳过无效Duplicate和其手工V_MTE2；队列Alloc/Free、EnQue/DeQue
继续负责复用及搬入到计算的依赖。尾N仍先填-inf并等待V_MTE2，防止未写列参与Max。
不将“手工预填fence减少”误写成“所有同步都删除”。

改动两类消费者：宏块RowMaxConsumer，以及P01原生小K和残余D01共享的SmallKConsumer。
生产者、host路由、ring布局/大小、全局屏障、partial布局和最后ReduceSum不变。
这也覆盖未被R04大K宏块接管的小K原生路径；不猜测它们对应哪个隐藏点。

代价是UB增加：宏块acc为32KiB，微块消费者acc为64KiB。
M=8192时微块消费者总申请181280B，低于模型192KiB限制；该容量及编译器实际分配仍需
平台编译确认。未增加GM workspace，也未占用更多ring槽。

## R06_MACRO_MMAD

维持R04的AM=128、BN=256、K1=256、K0=64和2×2输入复用。
每个K0片把A排为完整`ar×kr0` Zz、B排为完整`kr0×br` Zn，发出一条
`Mmad(m=ar,n=br,k=kr0)`。L0C按完整宏块NZ存放，不再是四个独立NZ小矩阵。

A搬运选择M/K分形中较短的循环轴；K循环时，LoadData的dstGap用于跨越其余K分形。
B同理，并跨完整br一次repeat搬运。全部偏移按实际ar/br/kr0/kr1计算，不能在尾K
继续用原微块保留间隙，也不能把TA/TB物理布局混为一类。所有repeat均小于255。

将整块C按原四个微块发布给未修改的消费者：

- 源NZ偏移为`(no/16)*ar*16 + mo*16`。
- Fixpipe源分形步长为`ar`，不是局部输出微块的`mr`。
- 目标仍为原宏槽内的`ci*TM*TN`，dstStride仍128。
- 单个完整宏块仍四次Fixpipe，之后一次READY；每个AIV读完才FREE。

保留M_FIX、FIX_M、MTE1/M依赖及小输出PIPE_M；不启用unitFlag。
全部活跃C分形都会搬出。每个输出元素仍按原K0顺序累加；实际Cube舍入是否与父版
一致不能由CPU模型保证，需平台精度反馈。

L1、L0A、L0B、L0C容量保持393216/32768/65536/131072B，UB与R04一致。
在B1,M128,N256,K256,cores1的控制例中，Mmad API调用16→4，LoadData调用64→32，
GM输入196608B、L0输入196608B、C写131072B以及READY/FREE均不变。
这是压缩指令组织，不是减少矩阵乘的FLOP；不能据此宣称速度4倍或2倍。

## 验证与判定

对R04/R05/R06执行相同扩展用例，包括四布局、双dtype、负数/零、M/N/K同时尾块、
跨宏槽复用、N分片、B多批次、M8192、原生K32/64/128以及大K路径。
每版256次普通运行、128次重复输出核对，三版普通输出记录逐位一致；
另有3次已知数值限制复现。4494调度、7560guard边界检查保留。

CPU模型新增队列分配时清除初始化标记，避免旧UB内容掩盖遗漏写入；新增本地地址
对齐和容量检查。M_FIX完成等待清除已完成M指令的pending状态，支持原小K生产者
每块MMAD后等待M_FIX的真实结构，不修改它的生产代码。

三个宽N控制例的R05行归约调用均减少到1/4；R06在宏块控制例减少MMAD与LoadData
调用，残余及小K控制例保持R04计数。负向检查故意删除尾N填充、写错宏块L0C步长，
要求检查器拒绝。最终运行结果与SHA绑定见CHECKS.json。

优先提交R06，再单独提交R05。比较全部15点及最新T；R06重点验证已有宏块域，
R05覆盖更广的原生消费者。任一失败先依据编译日志或失败点回退对应单项。
无CANN/NPU环境，本轮没有真实性能预测或本地设备通过结论。

## 官方接口依据

- [Load2D](https://www.hiascend.com/document/detail/en/CANNCommunityEdition/900/API/ascendcopapi/atlasascendc_api_07_00169.html)：A2路径、512B分形、srcStride/dstGap及repeat约束。
- [Load2D V2适用范围](https://www.hiascend.com/document/detail/en/CANNCommunityEdition/910/API/ascendcopapi/docs/en/api/SIMD-API/basic_api/cube_compute_ISASI/cube_compute_load/Load2DV2.md)：明确A2不支持。
- [Mmad](https://asc.gitcode.com/api/SIMD-API/basic_api/cube_compute_ISASI/mmad_compute/Mmad.html)：A2 Zz/Zn/Nz布局、对齐及小块K累加依赖。
- [Fixpipe](https://www.hiascend.com/doc_center/source/en/CANNCommunityEdition/900/API/ascendcopapi/atlasascendc_api_07_0251.html)：源NZ分形步长和NZ2ND搬运。
- [Pipe与同步](https://www.hiascend.com/document/detail/en/CANNCommunityEdition/910/programug/Ascendcopdevg/docs/en/guide/programming_guide/programming_model/ai_core_simd_programming/cpp_tensor_programming/static_tensor_programming.md)：队列管理前向/复用依赖。

以上资料在2026-09-26查阅，用于约束实现，不用文档中的独立性能示例预测本算子成绩。

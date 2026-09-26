# R01反馈后的两个独立实验：R02 / R03

用户明确标注R01，15/15 Pass，同T复算31.85356172，P01历史32.09562559。
点9–11的分数贡献共+1.70769，点12贡献−1.41479，总分仍低0.24206。
点15在D01为37.54μs、R01为115.13μs，但没有shape/kernel记录，不能断言其路由。
本轮按用户要求无测试环境继续平台提交，冻结R01源码和历史记录。

## R02_MACRO_RING：改变发布粒度

R01已经在L0C完成2×2微块，但两个GM槽每个只存一个微块。发布第3、4块前，
AIC必须等AIV释放当前槽，才能继续推进。这个同步结构是源码事实；它是否造成
点12回退仍是假设。R02一次发布一个宏块，两个槽各容纳4个微块。

保持R01公开guard、pM/pN/blocks、输入搬运、Mmad、L0C、归约算术不变：

1. 每宏块开始写GM前等宏槽FREE（前两个宏块无需等）。
2. 四个Fixpipe各写宏槽内独立区域，最后才发一次READY。
3. 两AIV各等一次READY，按旧mo/no顺序消费；最后一份MTE2读完后才发FREE。
4. AIC必须收齐两AIV的FREE才能复用整个宏槽；退出回收两个槽的未消费credit。

单完整宏块：Fixpipe仍4次，逻辑C写/读字节不变，READY发布4→1，AIV
READY等待8→2，FREE设置8→2，AIC FREE等待总数4→1。不引入新的flag ID。
GM ring每组65536→262144B，最多64组共16MiB；L1/L0/UB不增加。
代价是GM/L2工作集更大、消费必须等待完整宏块输出；尾宏块不足4块时收益更少。
禁止用事件次数减少推断设备速度。R02不负责扩展R01的覆盖范围。

## R03_RESIDUAL_DENSE：补上未覆盖的对齐域

R03是R01的另一个子版本，**不包含R02宏槽改动**。入口先尝试完整R01，
再尝试D01的K128单微块路径，最后保留P01。D01新增路径仅接管：
`D01Eligible && !R01Eligible`，并执行相同B、核数、dtype、输入规模约束。
此差集包括M<128、N<256或宏块数少于核数的一部分对齐密集shape。

R01Qualified：M≥128,N≥256,K≥256,M/N%16=0,K%32=0，宏块数≥核数。
D01Qualified：M/N≥16、M/N%16=0、K≥256、K%32=0。
二者共同要求B1..64，M/N/K≤8192，输入规模≤2^26。

输入布局和算术继承D01；对输出16×16块数小于10的Mmad补充官方要求的PIPE_M
依赖。该修正必须记录，不能称新分支与D01逐字完全相同。R01正文原样保留，
因此R01已覆盖的形状不被新增D01分支抢走。没有隐藏点号、数值判断或输出拼接。
若点15改善且点9–12维持R01水平，支持覆盖不足假设；否则该假设仍未成立。

## 验证计划与边界

执行R01/R02相同producer/consumer源码模型，逐位比对输出和输入逻辑流量，
检查四布局/双dtype、负数和零、宏块尾、单/双/多次ring复用、N分片、多个batch。
在CPU模型中新增环槽所有权审计：每次READY冻结写入量，两个AIV均需读完
各自半块才能发FREE；下一次Fixpipe不得覆盖尚未释放的槽。用故意提前FREE
的错误版本验证检查器能拒绝错误。这仍不是硬件缓存/同步仿真。

R03执行实际公开guard，分别运行R01或残余D01生产/消费路径，并证明新增分支
与R01覆盖域互斥、非对齐和小K仍回到P01。保留FP32极端数值限制。

先提交R02，另一次单独提交R03；任一失败都可定位到一项机制。现在不组合。
不增加测试环境前置条件；新文件仅完成离线检查，等待平台编译/正确性/时间。

依据：[CANN9.0 CrossCoreSetFlag](https://www.hiascend.com/doc_center/source/en/CANNCommunityEdition/900/API/ascendcopapi/atlasascendc_api_07_0273.html)、
[CrossCoreWaitFlag](https://www.hiascend.com/doc_center/source/en/CANNCommunityEdition/900/API/ascendcopapi/atlasascendc_api_07_0274.html)、
[Mmad小块同步](https://asc.gitcode.com/api/SIMD-API/basic_api/cube_compute_ISASI/mmad_compute/Mmad.html)。
采用已装载算子设计/性能优化技能的方法，适配为比赛单文件和用户授权的无卡检查。

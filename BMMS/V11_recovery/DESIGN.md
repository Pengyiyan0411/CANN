# R09 / R10：沿用R08，通过独立实验继续推进

本轮收到明确反馈：R08为截图对应版本，15/15 Pass；R07在**点5运行阶段TLE**。
结果、原图与最新T见 `V11_results/2026-09-26_r07_r08_submission`。
R08点13/14较R04的单次耗时下降12.33%/6.15%，值得复核，尚未排除测量波动。
R08作为开发父版；R04仍冻结，R07不合并。R09、R10互相独立，均从R08派生。

## 源码排查及R07诊断

| 阶段 | 发现与处理 |
|---|---|
| 切分 | R07遍历网格并逐任务累计每核工作量。局部工作更均衡的模型成立，但运行成本较高，且平台出现TLE。停止沿用该搜索。 |
| 搬运 | R08小K已成包；残余大K仍按64×128微块握手。R09扩大GM队列并复用已通过的小K消费者协议。 |
| API/算术 | 维持完整K累加、相同MMAD和Vector归约次序。R05/R06收益未证明，继续不合并。 |
| 片上资源 | R09不增加UB/L1/L0；仅残余GM ring变大。R10只改host规划，device源码不改。 |
| 同步 | 核对生产者与两AIV的包次序、最后不足四块的发布与释放、跨task/batch序号、最后事件回收。R07硬件超时尚无根因证据。 |

`diagnose_r07.py`抽取实际MakePlan，在本地Windows/g++执行O2和O0微基准。
每形状5组、每组100次调用，三版在同一进程中交替测量，结果保留全部样本摘要。
R07例如B1/M8192/N8192/K256、64核组，需要509个候选和78244次任务访问；
即使最后返回原计划也支付这些开销。20核组的B1/M4096/N4096/K256是123候选、5828次任务访问。
这说明host规划确有代价，**不能把本地CPU耗时冒充平台NPU耗时或点5TLE根因**。
精确测量见 `R07_HOST_DIAGNOSIS.json`，报告中的核数是合成输入，不是实际评测核数。

静态检查没有找到新增未匹配的READY/FREE：R07原样保留device循环与flag，实际task遍历
也已做独立覆盖核对。宏块入口已有`__schedmode__(1) __mix__(1,2)`，核组数量不变。
READY/FREE使用4–7，官方文档列出的SyncAll硬同步占用11–14，没有直接ID重叠。
但这不证明真实硬件不会死锁，也不能排除其他运行阶段问题。仅有点号和阶段，没有
点5shape/故障日志，不能认定它走哪条路径或将TLE归因于某条指令。

同步语义以官方[CrossCoreSetFlag](https://www.hiascend.com/document/detail/en/CANNCommunityEdition/910/API/ascendcopapi/docs/en/api/SIMD-API/basic_api/sync_control/inter_core_sync/CrossCoreSetFlag_ISASI.md)
及[CrossCoreWaitFlag](https://www.hiascend.com/doc_center/source/en/CANNCommunityEdition/900/API/ascendcopapi/atlasascendc_api_07_0274.html)
为依据（2026-09-26查阅）。mode2要求配对的两个AIV都释放后AIC才能继续，保留这一协议。

## R09_RESIDUAL_PACKETS

在R08基础上，仅改`bmms11d`残余大K路径的输出握手及相应GM工作区。
原生小K、宏块路径、公开shape guard、host分派与所有算术均保持R08。

- 每个GM包容纳四个64×128输出微块，两个包槽。
- `packet=seq/4`、`slot=packet%2`、`tileSlot=seq%4`，输出地址为
  `((group*2+slot)*4+tileSlot)*TM*TN`。
- 第三个包起，在包的第一次Fixpipe前等待旧包FREE；第四次Fixpipe后发送READY。
- AIV直接使用R08的`SmallKPacketConsumer`，各自在读完第四块后发送FREE。
- 最后不足四块时先显式发布尾包，再回收FREE；seq跨任务/batch连续。
- 残余生产者仍只有**一个**L0C：每个下一微块开始前等待原FIX_M事件，不能把它
  跟GM包槽的释放合并。K128双缓冲、输入复制、LoadData和MMAD完全沿用原代码。

残余GM ring从64KiB/核组增为256KiB/核组，64核组上限对应16MiB ring。
片上空间和partial布局不变。对16块长流，READY理论计数16→4、两个AIV的FREE总数32→8；
输入字节、MMAD、Fixpipe、C读写和归约计数应保持不变，由实际源码控制例核对。
短流首包等待及更大GM工作集可能抵消收益，因此这是待测候选。

## R10_SINGLE_WAVE_GRID

R10也是独立R08后代，不含R09。仅替换宏块MakePlan；kernel完全维持原样。
不同于R07，只有**原计划恰好一个任务对应一个已启动AIC组**时才考虑调整，即
`original.tasks == cores`。其他情况原样返回原Plan。调整后B×pM×pN仍严格等于cores，
任务数、启动核数、每核任务数完全不变，不引入第二轮任务。

令g=cores/B，只遍历满足pM×pN=g的因数对，最多64次循环。每候选用整数闭式公式计算
最忙核宏块数、有效M×N单元数及输入单位数，没有任务遍历数组、浮点评分或缓存。
三项峰值都降低至少12.5%才接受；按峰值宏块数、单元数、输入量、较小pN顺序打破平局。
12.5%是结构性改动门槛，不是测评波动估计或提速保证。

尾块公式：长度x，tile宽t，共T=ceil(x/t)块，分p份。每份tile数为q或q+1。
若p=1，最大有效长度为x；若T%p=1，唯一长分片在最后，最大长度为x−(p−1)qt；
其余情况至少有一个满长分片，最大长度为ceil(T/p)t。独立枚举所有分片核对这一公式。
完整笛卡尔网格覆盖M、N的最大分片组合，故可得到峰值cells和input的精确值。

合成B1/M4096/N4096/K256、20核组，原20×1改为5×4，最忙核宏块数32→28，
仍只有20个任务。R07同例会选5×16、80个任务。原本24任务的B1/M1024/N1024、20核组，
R10完全不改。增加pN仍增加partial写读及最后Max循环，闭式模型不将它视作免费。

R10不是已确认的TLE修复；它是去掉高开销搜索、保持任务轮数的受限重试。
如果平台仍超时，停止该候选并保留R08/R09路线，不继续盲目叠加调度改动。

## 验证与复现

```bash
python V11_recovery/build.py
python V11_recovery/diagnose_r07.py
python V11_recovery/run_checks.py
python V11_recovery/update_docs.py
python V11_recovery/package.py
```

源码CPU检查三版同测四布局、双dtype、负值/零、M/N/K尾块、小K及残余大K、跨任务/batch。
新增残余尾包1/2/3块、超过两包槽复用、K4096、长M短N，并实际运行一个R10切分改变的形状。
故意提前FREE及移除残余尾包READY，要求检测器分别捕获所有权错误和等待超时。
另外逐核遍历宏块，检查任务所有权、全局计算/输入总量、峰值、未改变任务及启动核数。

精确执行结果、版本SHA及检测器SHA以`CHECKS.json`为准。本地不具备CANN编译/NPU环境；
CPU模型不能证明硬件流水、舍入、缓存或耗时。现有三个消去/BF16中间溢出限制仍需记录。

## 测评波动与下一轮

建议先R08→R09→R08，再R10→R08。提交包中的R08控制与已通过源码逐字节相同。
每次保存完整15点和当次T，使用候选前后控制的逐点原始耗时判断方向，再统一最新T复算分数。
控制区间内的变化记为未分辨，接近边界时复测；区间外一次观察也不称统计显著。
不做全点比例校正，不把不同版本的单点最低耗时拼作一份成绩。当前没有相邻控制复测，
故R08局部收益尚未完全排除噪声。本轮继续平台提交，不要求新增算力。

# R11 / R12：从已确认有收益的R10继续

R10只有宏块host网格改变，device源码与R08相同。用户报告R10收益稳定，典型点10
106.62→84.10μs。它支持继续调整任务分配，但没有隐藏shape和profiler，不能据此
定位具体硬件流水瓶颈。本轮两份候选都独立从R10派生，不合并R09，也不互相叠加。

## R11：消除符合条件的短第二轮任务

原R10只调整`tasks == cores`的单轮网格。R11先原样调用R10的MakePlan，保留其全部
单轮决策；仅当B整除cores、启动核数仍等于cores、旧tasks大于cores时再考虑新网格。
保持原宏块AM=128、BN=256、K切分、核数、Cube/Vector代码和各条分派guard。

1. 对原网格只遍历一次任务，计算最忙核的宏块数、有效C元素数、A/B输入长度单位。
2. 枚举`pM*pN = cores/B`的因数对，候选恰好每核一个任务。
3. 用R10已有的闭式尾块公式评估候选；三个峰值都至少下降12.5%才接受。
4. 依次按宏块数、C元素数、输入长度、较小pN选优；没有合格候选则返回R10原计划。

这里12.5%是结构上的筛选门槛，不是测量噪声阈值。原任务总数小于2*cores，因此
旧网格遍历最多126个任务，且只做一次；没有恢复R07每个候选都遍历全部任务的搜索。
候选的全局宏块、C元素及输入长度总量保持不变，变化的是核间峰值和任务轮数。
部分候选pN增加，相应partial空间和最终N合并成本也会增加，需要平台验证净收益。

独立枚举6758组网格，154组在R10上进一步调整，唯一覆盖、峰值公式和全局总量检查通过。
以下全是合成例子，不能对应隐藏测试点：

| B×M×N×K | 核组 | R10网格/任务数 | R11网格/任务数 | 最忙核宏块数 |
|---|---:|---|---|---|
| 1×512×768×256 | 6 | 4×2 / 8 | 2×3 / 6 | 4→2 |
| 1×1024×1024×256 | 20 | 8×3 / 24 | 5×4 / 20 | 3→2 |
| 1×4096×4096×256 | 20 | 5×4 / 20 | 原样保留 | 28→28 |
| 1×384×768×256 | 5 | 3×2 / 6 | 无可用因数网格，保留 | 3→3 |

[实际源码host微基准](HOST_BENCH.json)采用本地Windows g++ -O2、5组×1000次。
第一、二例R11分别约0.103/0.256μs；本组最慢例为1×8064×8192、64核组，约1.295μs，
该例最终不改网格。非常小的R10数值受微基准开销影响，不能作为设备时延或TLE证明。
R07点5运行TLE的根因依然未知，R10通过也不等于确定了R07的根因。

## R12：把N分片合并分摊到多个AIV

保留R10的host计划、Cube生产者、ring协议和第一阶段Vector处理。原流程第一阶段
写`partial[B,pN,M]`并同步，然后每个batch只由一个AIV读取全部N分片、Max、ReduceSum。
R12在`pN >= 4 && M >= 1024`时，增加一段行块并行的N合并：

1. 保留原第一阶段MTE3完成等待和`SyncAll<true>()`。
2. 每128行一个job，按`job % (2*blocks)`分配给AIV。每个job按原ns次序合并所有pN
   分片，使用已有的128个float的VECOUT runningBuf；写入追加的`scratch[B,M]`。
3. 等待本核写回完成，然后所有AIV参加第二个`SyncAll<true>()`，包括没有job的AIV。
4. 最后仍由原来的一个AIV读取每个batch的**完整M向量**，调用原来的ReduceSum。
   不做分块求和，不改变M方向求和次序。gate关闭时执行原串行N合并。

原始N分片不覆盖，scratch每行只有一个写者；行块和尾部均满足原M对齐条件。
对输入DMA→Vector、Vector→DMA、输出DMA→buffer复用均保留显式事件顺序。
READY/FREE仍是4–7，没有新增自定义跨核flag。入口仍为MIX(1,2)、batch调度，
核组数来自运行时；这里用的是A2已有的无config硬同步接口。

代价必须计入：

- 所有宏块启动都额外申请`B*M*4`字节GM，即使并行gate关闭也申请；契约上界2MiB。
- gate开启时增加一次B*M写回、一次B*M读取，以及一次AIV全局同步。
- 128行小DMA和循环发射也有成本；若原归约占比小，可能没有收益甚至变慢。
- UB/L1/L0申请不增加；这不代表GM交通不增加，也不代表整体耗时必然下降。

源码CPU归约检查中的B1/M1024/pN4、20核组例：最忙AIV读取4096→1536个float，
总读取4096→5120，额外写1024，同步次数1→2。B1/M8192/pN16、64核组例：
最忙AIV读取131072→10240。这些是完整末段的元素计数，不是硬件带宽或提速估计。
这些隔离阶段的合法Plan用于检查末段，不声称均为MakePlan实际选择的网格。

## 检查与边界

- R10/R11/R12各452次普通源码CPU执行、226对重复运行，普通输出三版逐位一致。
  包括双dtype、四布局、全负值/零、长K、尾块、跨任务/batch、ring回绕，以及实际会
  触发R11网格改变和R12并行合并的输入。
- 每版另有22次隔离归约检查；R12有14次进入并行，另8次验证门槛关闭。
  覆盖M=1040尾块、M=8192、B=64、pN=32、空闲AIV、单核多job及反向线程启动。
- scratch写者、唯一写入、读前同步、覆盖范围、原分片不变和总读写量均独立核对。
  R10/R11隔离helper逐字复制原归约末段；正常Process仍执行原源码。
- 删除第二同步被检测为读前同步缺失；漏最后一个N分片被检测为参考结果不符。
- 每版4494项原调度与7560项guard检查通过。片上峰值保持UB 132256、L1 393216、
  L0A 32768、L0B 65536、L0C 131072字节。
- 原有3项FP32消去/BF16中间溢出限制仍复现，未宣称全输入域精度达标。
- 本地未CANN编译、未NPU测试。CPU模型不能验证硬件流水、cache、舍入和耗时。

[CHECKS.json](CHECKS.json)绑定源码和检查器SHA；[diff R11](R11_SINGLE_WAVE_EXPAND.diff)、
[diff R12](R12_PARALLEL_N_MERGE.diff)给出相对R10的全部改动。

## 官方接口依据

[华为SyncAll接口](https://www.hiascend.com/document/detail/en/CANNCommunityEdition/910/API/ascendcopapi/docs/en/api/SIMD-API/basic_api/sync_control/inter_core_sync/SyncAll.md)
及[官方API镜像](https://asc.gitcode.com/api/SIMD-API/basic_api/sync_control/inter_core_sync/SyncAll.html)
说明A2支持无config硬同步，MIX(1,2)可用，true限定AIV；config重载的硬件支持范围不同。
本版沿用已使用的无config调用和batch调度，没有引入config重载。
[CrossCoreSetFlag](https://www.hiascend.com/document/detail/en/CANNCommunityEdition/910/API/ascendcopapi/docs/en/api/SIMD-API/basic_api/sync_control/inter_core_sync/CrossCoreSetFlag_ISASI.md)
用于核对原mode2协议。文档核对不替代实际安装版本编译和硬件测试。

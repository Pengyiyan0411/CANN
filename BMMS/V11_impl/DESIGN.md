# V11 R01：重新建立可检验的密集计算路线

## 决策依据

用户确认最新 15/15 Pass 截图为 F01_STREAM_M。相同截图 T 下 F01 为
21.121478953 分，P01 历史耗时复算为 32.095625586 分；14/15 点变慢，
点 14 为 P01 的 13.6117 倍。P01 不是同轮重测，截图不提供 shape、实际
kernel 或 profiler，因此不能从点号反推瓶颈。F01 停止作为主线，F02 未测。

原路线错误：统一路径抹掉了已有小规模专用分支；把 streaming/少分配完整 C
当作新优势，但 P01/D01 已有分块消费；V9 的 AM/BN 只是遍历分组，每个
输出小块仍独立重新搬入全部 K 的输入。不能继续用更多同类 tile 扫描替代诊断。

本版只验证一个新假设：真正复用 L1、L0 的 A/B 操作数能否改善密集计算。
不宣称已识别硬件主瓶颈，也不宣称最优。R01 无 SDK per-tile KFC；继承 P01
的其他分支不变。没有直接套用 CATLASS 库，也没有修改默认 MIX 模式。

## 接口与数学契约

仍为官方单文件 `code/kernel.asc`，原 `run_kernel` ABI，FP16/BF16 输入，
FP32 输出。B∈[1,64]，M/N∈[1,8192]，K∈[32,8192] 且 K%8=0，
B*M*K、B*N*K≤2^26。支持 TA/TB 四种布局。核数按 P01 的公开参数处理。
结果为每个 batch 的 `sum_m(max_n(sum_k(A*B)))`，不可交换 max 与 K 求和。
官方 golden 使用实际量化输入做 FP64 dot/max/sum 后转 FP32。

R01 guard：M≥128、N≥256、K≥256，M/N%16=0、K%32=0，
`B*ceil(M/128)*ceil(N/256) >= cores`，且非 Tiny/Resident。
其余输入完整回退冻结 P01，避免只为省搬运牺牲可用并行度。
分支仅依赖公开 shape/dtype/layout/核数，不读取数据值、测试编号或参考结果。

## 真正复用的层级

- 每个宏块 AM=128、BN=256，含 2×2 个 TM=64、TN=128 的输出小块。
- K1=256：一次 GM→L1 搬 A[128,256] 和 B[256,256]，共同服务四个 C 小块。
- K0=64：一次 L1→L0 搬两个 M 片 A、两个 N 片 B；每个操作数用于两个 Mmad。
- 四个 L0C 各 32 KiB，在完整 K 范围累加后才输出 FP32 C。没有 split-K、
  FP16 C 或分片 max。L0C 格式用实际 mr/nr 紧凑存放，保留固定容量槽位。
- 宏块按 M→N，小块按 mo→no 输出。两个 GM C 槽供两个 AIV 分行消费，
  保留跨 N 的 row-max，最后按 P01 方式合并 N 分片并 sum 完整 M。

| 存储 | 显式字节 | 用途 |
|---|---:|---|
| L1 | 393216 | A/B 的 K1 双缓冲，低于 512 KiB |
| L0A | 32768 | 两个 K0 槽，每槽两个 M 片 |
| L0B | 65536 | 两个 K0 槽，每槽两个 N 片 |
| L0C | 131072 | 四份完整 K 累加；占满 128 KiB |
| AIV UB | 33440 + 12*M | cq/acc/rows/running/output 及最终 merge/tmp/sum |
| GM ring | 65536*blocks | 每核组两个 64×128 FP32 槽 |
| GM partial | 4*B*pN*M | N 分片 row-max |

UB 最大为 131744 字节（M=8192），固定 buffer 按 32 B 对齐。
这里按比赛 A2 目标规划，不冒充运行时查询到的其他芯片资源。

## 同步与所有权

L1 的两个槽由 MTE2_MTE1 ready、MTE1_MTE2 free 管理。一个槽的所有
K0 操作数读完才发 free。L0 的两个槽由 MTE1_M ready、M_MTE1 free
管理；四个 Mmad 全发出后才释放共享输入。小输出块按官方要求插入 PIPE_M。
完整 K 后 M_FIX；每份 Fixpipe 后发 READY；两 AIV 的 MTE2 读完后发 FREE。
生产者覆写 ring 前等待两份 FREE。四份 C 发出后 FIX_M；下一宏块允许先
预装输入，第一次 Mmad 前必须等待 C 的 FIX_M。退出时回收所有本地和跨核 credit。

调度单位为宏块，producer 和 consumer 的 M/N shard 边界必须同时使用
AM/BN；不能把旧微块 mTiles/nTiles 与新宏块复用混用。

## 可证伪的收益与代价

B=1,M=128,N=256,K=256,cores=1：D01 逻辑输入搬运 393216 B，
R01 196608 B；GM→L1 API 次数 16→2。C 写和读的逻辑有效字节不变。
实际 HBM/L2 流量、速度必须用设备验证，不能把逻辑减半写成两倍加速。
K0=64 增加 Mmad 次数，占满 L0C 限制跨宏块 C 双缓冲，尾宏块复用较少；
这些可能抵消搬运收益。它与 D02 的 K64 小 DMA 完全不同：本版 K1 仍为256。

## 验证与后续选择

离线执行真实 producer/consumer 的 C++ 源码，检查布局、bounds、event credits、
负数 max、N split、尾块、重复顺序、资源和实际 API 逻辑搬运计数。CPU 模型
不模拟真实缓存可见性、Cube 舍入、编译器及设备调度；不是 CANN 编译通过。
FP32 完整 K 仍有消去/溢出精度反例，结构重写不修复该已知数学限制。

下一次上卡只比较冻结 P01 和 R01，先精度再同输入 ABBA msprof。记录实际
kernel 名、Task Duration、PipeUtilization、SDK/SoC/核数和源文件 hash。
若 R01 搬运减少但耗时不降，根据 MTE2/MTE1/M/FIX/AIV 数据判断是算术、
发射还是消费瓶颈；不继续盲扫 K 或再统一小规模路径。准备脚本有总时限。

## 依据与适配

采用已装载的 ascendc-operator-design/testcase-gen/performance-optim 的
设计、内存、流水和同输入对照方法。code-gen/compile-debug 子 skill 本机缺失，
且用户要求无卡先实现、官方单文件提交，故不建立 whl/ascend-kernel 工程，
不把离线检查冒充技能要求的完整设备验收。

- [CANN 9.0 Fixpipe](https://www.hiascend.com/doc_center/source/en/CANNCommunityEdition/900/API/ascendcopapi/atlasascendc_api_07_0251.html)：A2 CO1→GM；不可套用新芯片直接 L0C→UB。
- [官方 Mmad](https://asc.gitcode.com/api/SIMD-API/basic_api/cube_compute_ISASI/mmad_compute/Mmad.html)：对齐与小块 PIPE_M 约束。
- CATLASS v1.4 commit `bcb3e52b6be3004b28996fb48af65ce48710c8f4` 的 `block_mmad_preload_async.hpp`：K1/K0 分层及槽位所有权参考，未依赖其外部头文件。

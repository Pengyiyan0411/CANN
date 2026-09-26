# R11 / R12提交包：附原样R10控制

先测 **R11_SINGLE_WAVE_EXPAND.asc**，再单独测 **R12_PARALLEL_N_MERGE.asc**。
建议顺序：R10_CONTROL → R11 → R10_CONTROL → R12 → R10_CONTROL。
每次选一份asc整体替换官方`code/kernel.asc`，沿用官方main/CMake，不手动叠加，
不加ASCENDC_CUBE_ONLY。两份候选均独立从R10派生，不包含R09。

- R10_CONTROL.asc：用户已确认收益稳定、15/15 Pass的R10字节相同副本。
- R11：保留R10已有单轮网格，仅消除符合条件的短第二轮任务，不改device源码。
- R12：宏块路径按行块并行合并N分片，最后仍执行原完整M ReduceSum；不改R10网格。

R10典型点10为84.10μs，R08为106.62μs，下降21.12%。本次同T复算总分R10为
36.170754、R08为34.805192。用户报告收益稳定，但只有一张逐点原图，未虚构重复统计。
R09仅有“没啥收益”的定性反馈，未伪造时延或通过数。R07点5运行TLE根因未确认。

本轮R10/R11/R12各452次普通源码CPU执行、226对重复运行和22次隔离归约检查通过；
6758组网格核对通过，两项故障注入被捕获。普通输出三版逐位一致，3项既有极端数值
限制仍然存在。本地未CANN编译或NPU测试，R11/R12尚未取得平台结果。

R11可能增加N分片带来的partial成本。R12所有宏块启动额外申请B*M*4字节GM
（上界2MiB）；并行gate开启时增加GM读写和一次AIV全局同步，可能抵消并行收益。
UB/L1/L0不增加。CPU模型不能证明硬件时延与流水正确性。

保留每次完整15点及当次T，和相邻R10控制逐点比较；波动范围内先不认定收益，
不全局比例修正，不拼接各版最短点。若TLE，记录点号、运行/编译阶段和报错文字。

SHA256：

- `R10_CONTROL.asc`：`cd8f8d6383ca24d0e46ae14757e1fce8b639da4123cc3a2a0875664564fb3600`
- `R11_SINGLE_WAVE_EXPAND.asc`：`425db189f068ad963dadf2c537a96118b33a5035ef47c5e43dad2f81fd0ad223`
- `R12_PARALLEL_N_MERGE.asc`：`c8ff69939a58da927f6df5ee1515725d131ab81f20243275c86b65b70e6394c5`

MANIFEST和CPU_CHECKS绑定相同源码；完整设计、检查器、原始反馈随CANN/v11归档。

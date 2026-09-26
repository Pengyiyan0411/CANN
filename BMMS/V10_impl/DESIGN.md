# V10：按精简方案实现流式融合

日期：2026-09-26。输入方案是用户提供的 `BatchMatmulMaxSum_V8_精简冲榜方案.md`，重新编号为 V10，避免覆盖已经提交的 V8/V9。

## 交付范围

- F01：同一个 SDK Matmul 流式内核，按 batch / M 分片。每次 Matmul 覆盖一个 M tile、当前 N shard 和完整 K；GetTensorC 后立即做 Max，全部 N 完成后 Sum。没有 Tiny、Skinny、Split-K 或旧 P01 路由。
- F02：计算内核相同，只在 `B * ceil(M / tileM) < cores && N >= 1024` 时允许 Split-N，每个 N shard 至少约两个 N tile。中间量是逐行 partialMax，最终先 Max 再 Sum。
- 第三轮暂不产生代码版本，等 F01/F02 的平台结果或 profiler 决定；不把未测的 tile/ping-pong 猜测称为优化结果。

默认计算块 64×128，K 基块优先 128、tiler 拒绝时尝试 64。小 M/N 缩至相应 16 对齐大小，仍走同一个内核。构建脚本只允许方案中的另外两组配置 64×256 和 128×128，供后续定向实验，不自动扩展版本。

## 与旧实现的真实区别

P01 本来就有 VECIN 输出接口，D01–D04 也没有分配完整 C。本版不能把“无完整 C 分配”描述成首次实现或测得的带宽收益。实际变化是删除复杂分流、固定 M-tile 流式生命周期、主路径使用很小的 partialY、仅在低并行度情况下拆 N，并统一处理任意 M/N/K 尾块。

Atlas A2 的 SDK MIX `GetTensorC(LocalTensor)` 可能通过系统 GM 暂存再搬入 UB。我们保证应用不分配完整 C，不保证硬件完全没有 C 的 GM 流量。使用同步 Iterate/GetTensorC；未宣称 Cube/Vector 已重叠。

## 调度与归约

主路径：B 足够时每个任务拥有整个 batch；否则按连续 M-tile 区间拆分。每个任务的 M-tile 和暂存在小 UB 向量，输出一个 FP32 partialY。GM partialY 用 64 字节槽隔离并发写，只有第一个 float 有效。所有 AIV 通过 `SyncAll<true>` 后，在同一次 MIX launch 内完成最终小归约，保持比赛 ABI 的单次 launch。

Split-N：每个任务持有一个 M tile 和连续 N-tile 区间；保存精确有效行的 partialMax。所有 N shard 的同一行先取最大，再 Sum(M)。不允许提前把每个 N shard 求和后合并。

task 数可以超过 core 数，采用持久循环；实际 block 数始终不超过调用方提供的 AIC 核组数。没有原子累加，分片映射和最终归约顺序固定。

## C 尾块布局

ND + sequential GetTensorC 的紧凑尾块按实际有效列数排布。只有一个 M 基块，因此 N 的遍历没有 M/N 二维分组解码问题。列数为 8 的倍数时按实际行距做 Vector Max + WholeReduceMax；否则用 Gather 将每一行的有效列搬到固定对齐的小 UB 行，剩余列填负无穷，然后归约。后者只用于一个 N 尾块，不增加 transpose kernel，也不读取 C 的无效填充。

此约定已核对官方 SDK 源码，仍需比赛 CANN 9 的实编和尾块实机确认。SDK 实现来源是固定提交的开发版，不能冒充比赛安装版验证。

## UB 与工作区预算

应用 UB 包括：C tile（默认 32768 字节）、runningMax[tileM]、tileMax[tileM]、分片内 tile 和（每个和占 8 float）、归约 scratch、尾块临时行/列索引/行索引/稀疏行结果、64 字节输出槽。Split-N 额外只分配两个 M 大小向量，且该路径的 M 受低并行度条件限制。host 计算实际总量并限制在 120 KiB，另给 SDK tiler 64 KiB UB，合计不超过 184 KiB。

系统 workspace 保留继承 ABI 的 16 MiB；应用 workspace 只有 partialY 或 partialMax，不包含应用 C 缓冲。直接按 batch 输出时应用 workspace 为零。

## 离线验证与设备边界

从最终单文件抽取真实 planner / device 类，经 CPU 语义适配器执行；检查输入布局、GM 越界、未初始化读取、唯一写入者、task 覆盖、UB 预算、Repeat 参数、同步参与者、逐位重复性。独立 golden 对实际量化后的 FP16/BF16 输入以 FP64 完成点积、Max、Sum，最后 FP32。

用例覆盖两种 dtype×四种布局、全负相似度、M/N/K 尾块、M=N=1、N=1、K=8192、B=64、M=8192、Split-N 启闭边界、N-shard 余数、多任务循环。CPU 结果不等于 CANN 编译、真实 DMA/KFC 同步验证或性能评估。普通 FP32 的强相消/BF16 溢出局限沿用已有审计结论；本版不是全数域精度认证。

## 依据

- [CANN 9 GetTensorC](https://www.hiascend.com/doc_center/source/en/CANNCommunityEdition/900/API/ascendcopapi/atlasascendc_api_07_0639.html)
- [CANN 9 Matmul 类型约束](https://www.hiascend.com/doc_center/source/en/CANNCommunityEdition/900/API/ascendcopapi/atlasascendc_api_07_0614.html)
- [官方 SDK 客户端](https://gitcode.com/cann/asc-devkit/blob/648a6018207d75af44c6865f96511bafadd90630/include/adv_api/matmul/matmul_client.h)：同步局部输出映射 GM，再 CopyToUB。
- [官方 SDK CopyCubeOut](https://gitcode.com/cann/asc-devkit/blob/648a6018207d75af44c6865f96511bafadd90630/impl/adv_api/detail/matmul/stage/copy_cube_out/copy_cube_out_fixpipe.h)：连续 ND 输出的 stride 为实际 baseWidth。

沿用已装载的 AscendC 开发、设计、测试用例及性能优化 skill。按用户无卡、单文件提交、多次提交的明确要求，交付离线检查后的候选；设备阶段留待提交，不搭建框架工程或申请算力。

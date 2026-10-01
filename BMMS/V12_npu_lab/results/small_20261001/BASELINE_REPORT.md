# 本轮基线快照

冻结代码：`BMMS_V12/v12_baseline_r41.asc`，SHA256 `1caf7870ac4154c0f555621ba9c41f4601c6ecee96cb2e8d0bf23acc4fc4f373`。

硬件：Ascend910_9362，20 Cube/40 AIV；CANN9，dav-2201。本机基线为r41直接ACL ABI执行结果，不是榜单参考耗时。CPU FP64用于精度，不作为NPU性能标杆。

第一轮基线精度：860配置、2580调用全部通过，见[r41_all.jsonl](r41_all.jsonl)。原输入规格、种子和二进制哈希在证据包的`cases/manifest.jsonl`中。

每轮性能均交错重测同一基线，不拿不同时间的最好值拼接。基线窗口、逐次task-time样本和真实kernel名见：

- 短点积：[r68_dot_summary.json](r68_dot_summary.json)。26配置，两个基线窗口，每配置100次，丢弃前20次。基线约0.98–1.06μs。
- 小矩阵初筛：[r69_micro_summary.json](r69_micro_summary.json)。32配置，每窗口80次、丢20次。
- 新形状留出：[r69_holdout_summary.json](r69_holdout_summary.json)。320配置，与r69交错对照。
- 交付版最终同批基线：[r72_final_summary.json](r72_final_summary.json)。168配置，每窗口100次、丢20次，与r72交错对照。

这些是带轻量msprof的设备任务计时。harness中的`host_call_mean_us`包含主机调度与同步，不用于任何加速比。

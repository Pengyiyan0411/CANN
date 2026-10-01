> Judge反馈：Case12 122.28μs，无明确收益，r21不晋升；主线仍为r19。以下为提交前实验记录。

# v12_r21 Case12候选

只提交v12_r21_case12_packet_tail.asc。父版为已接受的r19；Case8/15优化保留。

单宏块轮转分配，仅在峰值工作量门槛满足时启用；新增消费者采用显式最终Max尾部掩码。308组×3次精度通过，56组计划复验中17组切换且两轮全部正收益，其余39组回原计划。切换收益不能当成全部shape收益。

两例插桩memcheck无ERROR；原MMAD同类race报告及历史init限制尚未闭环，详见[完整报告](../V12_npu_lab/results/case12_20260928/REPORT.md)。真实Case12收益待Judge验证，主线保持r19。

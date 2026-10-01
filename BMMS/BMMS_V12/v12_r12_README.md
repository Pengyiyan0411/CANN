# v12_r12：已接受主线

用户已确认 Case15 稳定在约 **11.5 μs**、其余点基本无影响。r12 已晋升；冻结对照为 `v12_baseline_r12.asc`，与提交源 `v12_r12_splitk_adaptive_merge.asc` 逐字节一致。r03 保留为历史回退。[反馈记录](v12_r12_JUDGE_FEEDBACK.md)。

改动：只在Case15已确认的元数据范围启用8行一个向量核的K分片合并；N≤64或B转置时将完整K分片一次搬入L1，其余保留原生产流水。先完整K求和，再N max，最后M sum；不改变S和K分区。旧路径源码逐字节保留。

实际CANN编译通过；238个合成输入、每例3次全部通过。64个全布局样本两轮设备事件计时中位缩短21.53%/21.87%，50个额外尺寸两轮为17.92%/17.55%；部分小M形状接近零收益。这些不是比赛Case15成绩。普通构建memcheck未报告ERROR且有已记录的FFTS警告；racecheck因缺少插桩被工具跳过，不能计为通过（Case8复查已更正旧表述）。

后续 Case8 候选从 r12 派生。r10 有退化不推荐，r11 保留为结构对照。

- [详细实验报告](../V12_npu_lab/results/split_20260928/REPORT.md)
- [下一方向](NEXT_DIRECTIONS.md)：优先Case8阶段成本分析；Case2备用，Case6先定位route。
- [版本身份](v12_r12_manifest.json)

源码SHA256：`a845fd9538fe71d5f6284fced34781d8fb7e997105c51065a84b344818ddbd2b`

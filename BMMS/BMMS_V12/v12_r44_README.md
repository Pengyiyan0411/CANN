> Judge更新：Case12 113.68μs，无压力信号，MISS；Case11 82.82μs。主线仍为r41。下面保留提交前说明。

# v12_r44：仅检测Case12的r41展平门槛

**诊断版，不是冲榜版。正式主线是v12_baseline_r41.asc。**

提交 `v12_r44_probe_case12_flat_gate.asc`，只需这一个探针。Case11保持r41路径。

- Case12显著变慢（约正常5倍以上）且Pass：HIT，r41此前确实满足启用条件。
- Case12仍约115μs且Pass：MISS，r41未启用，应沿原r30路径优化。
- Fail或信号不清楚：不推断。

已完整编译；230配置、690次精度调用全部通过。26个构造配置公开入口校准：8 HIT为15.07～16.65倍，18 MISS为0.984～1.012倍。HIT实际1 Cube+2 AIV完成真实计算，不跳过计算或复用结果。

本轮r42、r43均在本地筛选淘汰，勿作为性能版本提交。没有新增sanitizer全量验收，历史限制沿用。

[实验与校准报告](../V12_npu_lab/results/wide_pingpong_20260929/REPORT.md)

SHA256：`07333c30adfcc8b75362500b3276e6a0d15da44f5428ea8dc87f4584c54fcbb2`。

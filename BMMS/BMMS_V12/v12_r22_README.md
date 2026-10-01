> Judge 两次 15/15 Pass，但 11/12 无明确收益；不晋升。主线仍为 r19。以下为提交前记录。

# v12_r22：按物理跨度选择NZ

父版为r19；r21不合入。本版仅在B1、M∈[1024,2048)、N∈[2048,8192]、K∈[1536,4096)且原R06 eligible时，按物理ND跨度决定是否复用r19的NZ kernel；不改变原planner。Case8/15和其他原实现保留。

348组、1044次数值通过；同卡独立性能验证及检测局限见[完整报告](../V12_npu_lab/results/c1112_20260928/REPORT.md)。两例memcheck无ERROR；race与历史init仍未闭环，不能声称完整sanitizer通过。实际Judge收益待反馈，r19保持主线。

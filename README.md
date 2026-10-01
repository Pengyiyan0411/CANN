# BatchMatmulMaxSum — V13

更新于 2026-10-01。已接受基线是 **v13-r1（原 v12-r72）**；Case12 O10 合并版 **r2 尚待 Judge 15 点测评**。

| 用途 | 文件 | 状态 |
| --- | --- | --- |
| 已接受基线 | [v13_r1_baseline_r72.asc](BMMS/BMMS_V13/v13_r1_baseline_r72.asc) | 用户确认 r72 的 Case2–4 有明显收益 |
| 下次提交 | [v13_r2_submit_compact.asc](BMMS/BMMS_V13/v13_r2_submit_compact.asc) | 300,552 字节，等待重新上传及 15 点测评 |
| 可读候选源码 | [v13_r2_case12_o10.asc](BMMS/BMMS_V13/v13_r2_case12_o10.asc) | 保留 r72，并合入去除诊断探针的 Case12 O10 路线 |

原 r2 返回的是 **HTTP 413 Request Entity Too Large**，请求在进入评测前被拒绝，不能据此判定 kernel 编译或精度失败。压缩版只移除注释及冗余空白，比原文件小 21.02%；CANN Host/Device 预处理结果已确认等价。服务器能否接收压缩版仍待实际重传确认。

## 最新证据

- [V13 状态及文件清单](BMMS/BMMS_V13/README.md)、[机器可读主线状态](BMMS/BMMS_V13/MAINLINE.json)
- [Case12 分支分析、形状证据与后续优化](BMMS/BMMS_V13/CASE12_BRANCH_ANALYSIS.md)
- [本地编译、精度、性能及 sanitizer 验证](BMMS/BMMS_V13/VALIDATION.md)
- [413 上传修复与预处理等价证明](BMMS/BMMS_V13/R2_UPLOAD_413.md)
- [压缩脚本](BMMS/V13_npu_lab/compact_submission.py)、[编译器等价验证脚本](BMMS/V13_npu_lab/c12_merge_20261001/verify_compact.py)

本地验证覆盖 93 个合成配置、279 次调用，其中 92 个配置通过。唯一严格抵消用例在 r1/r2 上以相同结果失败；race/init 检测也有尚未排除的报告。N=4096 的本地复测没有明确收益，N=4160/6080 有收益；队友报告的 Case12 约 20 μs 改善不能直接视为合并版已通过隐藏测试。

## 历史与复现

- [V12 源码与版本记录](BMMS/BMMS_V12/README.md)、[V12 主线演进](BMMS/BMMS_V12/MAINLINE.json)
- [Case1–15 分类与证据](BMMS/BMMS_Case1-15_分类与证据汇总_20260929.md)
- [V13 实验脚本与 harness](BMMS/V13_npu_lab/)
- [V12 NPU 实验计划](BMMS/BMMS_V12/NPU_EXPERIMENT_PLAN.md)
- [截至 V12 r06 的历史首页](BMMS/BMMS_HISTORY_THROUGH_V12_R06.md)（历史待测建议不代表当前状态）

归档保留版本源码、结果摘要、复现脚本及 V13 原始验证证据包。V12 的完整原始 profiler 数据库、编译产物和连接配置保留在本地；源码版本之间不因归档发生算法变更。

本次归档的逐文件 SHA256 见 [PUBLICATION_V13.json](PUBLICATION_V13.json)。

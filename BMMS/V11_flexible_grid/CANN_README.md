# CANN

BatchMatmulMaxSum算子源码、平台反馈和审计证据，位于v11分支。
R11/R12均15/15 Pass；R11点11降至100.71μs，点10保持83.75μs，成为工作基线。
同本次T复算R10/R11/R12为35.553080/36.937232/35.618585。R12暂不合并。
本轮每版只有一次逐点截图，R11尚未获得重复稳定性确认。

R13/R14独立从R11派生，允许至少75%可用核的较少核启动，分别处理剩余多轮/已有单轮。
device源码未改；先R11→R13→R11，再R14→R11，使用本次T及相邻控制比较。

- [提交包](BMMS/BMMS_V11_R13_R14_提交包.zip) / [使用说明](BMMS/BMMS_V11_R13_R14/README.md)
- [当前审计](BMMS/BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [R11/R12反馈](BMMS/V11_results/2026-09-26_r11_r12_submission/AUDIT.md)
- [设计](BMMS/V11_flexible_grid/DESIGN.md) / [检查证据](BMMS/V11_flexible_grid/CHECKS.json)
- [源码SHA清单](BMMS/ARCHIVE_MANIFEST.json) / [复现说明](BMMS/README.md)

各版464次普通源码CPU运行通过，8272组网格、42次独立穷举和两项规划故障注入通过。
既有3项极端数值限制保留，本地无CANN/NPU验证；R13/R14待平台结果。R07运行TLE根因未知。
历史源码、ZIP、原图和当时的交付文档保持原样。

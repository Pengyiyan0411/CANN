# CANN

BatchMatmulMaxSum算子开发归档，当前路线和证据位于`v11`分支。
用户已确认R02/R03均15/15 Pass；按最新T复算R02 33.7734、R03 33.3163。

当前待提交候选：[R04_MACRO_RING_RESIDUAL.asc](BMMS/BMMS_V11_R04/R04_MACRO_RING_RESIDUAL.asc)，
合并R02宏块发布和R03互斥残余分支，整体替换官方`code/kernel.asc`。

- [R04提交包](BMMS/BMMS_V11_R04_提交包.zip) / [使用说明](BMMS/BMMS_V11_R04/README.md)
- [当前审计](BMMS/BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [R02/R03截图与结果](BMMS/V11_results/2026-09-26_r02_r03_submission/AUDIT.md)
- [R04设计](BMMS/V11_merge/DESIGN.md) / [离线检查](BMMS/V11_merge/CHECKS.json)
- [归档文件SHA清单](BMMS/ARCHIVE_MANIFEST.json) / [复现说明](BMMS/README.md)

R04已完成173次普通源码CPU运行与分支、环槽检查，未CANN编译/未NPU运行，
原有3个极端数值限制保留。R04的实际平台性能待反馈，不拼接历史最短耗时作为成绩。
旧源码、结果和交付快照保留在BMMS目录与历史提交，v9/v10分支继续保存相应历史版本。

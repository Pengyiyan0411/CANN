# CANN

BatchMatmulMaxSum算子开发归档，当前路线和证据位于`v11`分支。
本轮截图15/15 Pass，按唯一前序候选归属R04；同最新T复算34.4965，
为当前记录内最好成绩，未核验全榜排名。原R04源码与ZIP冻结保存。

新候选分别从R04派生：先提交
[R06_MACRO_MMAD.asc](BMMS/BMMS_V11_R05_R06/R06_MACRO_MMAD.asc)，再提交
[R05_DEFERRED_MAX.asc](BMMS/BMMS_V11_R05_R06/R05_DEFERRED_MAX.asc)。
R06合并整宏块MMAD并改L0排布，R05复用N方向lane max并减少C块清填。两版互不包含。

- [提交包](BMMS/BMMS_V11_R05_R06_提交包.zip) / [使用说明](BMMS/BMMS_V11_R05_R06/README.md)
- [当前审计](BMMS/BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [R04反馈截图与结果](BMMS/V11_results/2026-09-26_r04_submission/AUDIT.md)
- [本轮设计](BMMS/V11_lowlevel/DESIGN.md) / [离线检查](BMMS/V11_lowlevel/CHECKS.json)
- [归档SHA清单](BMMS/ARCHIVE_MANIFEST.json) / [复现说明](BMMS/README.md)

R04/R05/R06各256次普通源码CPU运行通过，两个负向检查捕获预期错误。
原有3个极端数值限制保留；R05/R06未在本地CANN编译或NPU测试，实际平台成绩待反馈。
源码API计数下降不作为设备耗时预测。v9/v10分支及BMMS内历史交付文件保留原始状态。

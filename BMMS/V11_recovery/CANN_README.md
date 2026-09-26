# CANN

BatchMatmulMaxSum算子代码、平台反馈和审计证据归档，当前位于v11分支。
用户明确确认R08为15/15 Pass；R07点5运行阶段TLE，尚未确认根因。
按最新T5=1.90μs复算R08为34.808289，R04为34.276579。单次观测不代表已排除波动。

下一轮R09扩展残余大K四块输出成包，R10以闭式单任务网格替代R07逐任务搜索；
两版从R08独立派生。附字节相同的R08控制，先R08→R09→R08，再R10→R08。

- [提交包](BMMS/BMMS_V11_R09_R10_提交包.zip) / [使用说明](BMMS/BMMS_V11_R09_R10/README.md)
- [当前审计](BMMS/BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [R07/R08结果](BMMS/V11_results/2026-09-26_r07_r08_submission/AUDIT.md)
- [设计](BMMS/V11_recovery/DESIGN.md) / [检查证据](BMMS/V11_recovery/CHECKS.json)
- [归档SHA清单](BMMS/ARCHIVE_MANIFEST.json) / [复现说明](BMMS/README.md)

R08/R09/R10各444次普通源码CPU运行通过，6758组网格及25088项尾块公式核对通过。
两个故障注入被捕获。原3项极端数值限制保留；本地无CANN/NPU验证，R09/R10平台待测。
R10不标记为已修复TLE。历史源码、ZIP、原图和交付时文档保持原样。

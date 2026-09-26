# CANN

BatchMatmulMaxSum代码、平台结果与审计证据，当前位于v11分支。
R10已15/15 Pass，用户确认收益稳定；典型点10从R08的106.62降至84.10μs。
同最新T复算R10为36.170754、R08为34.805192。R10成为工作基线，R09不合并。

下一轮R11消除短第二轮任务，R12并行N分片合并；两版独立从R10派生，附原样R10控制。
先R10→R11→R10，再R12→R10，记录每次15点及当次T，保留完整测评波动。

- [提交包](BMMS/BMMS_V11_R11_R12_提交包.zip) / [使用说明](BMMS/BMMS_V11_R11_R12/README.md)
- [当前审计](BMMS/BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [R09/R10反馈及原图](BMMS/V11_results/2026-09-26_r09_r10_submission/AUDIT.md)
- [设计](BMMS/V11_single_wave/DESIGN.md) / [检查证据](BMMS/V11_single_wave/CHECKS.json)
- [归档SHA清单](BMMS/ARCHIVE_MANIFEST.json) / [复现说明](BMMS/README.md)

各版452次普通源码CPU执行、22次隔离归约及6758组网格核对通过，两个故障注入被捕获。
原3项极端数值限制未修复；本地无CANN/NPU验证，R11/R12待平台测试。R07点5运行TLE根因未知。
历史源码、ZIP、原图和交付时文档保留原样；稳定收益为用户复测报告，未伪造统计样本。

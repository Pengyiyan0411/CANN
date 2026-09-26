# CANN

BatchMatmulMaxSum算子归档，当前代码和证据位于v11分支。
用户确认R05/R06均15/15 Pass，并提醒测评波动。按最新T复算R04 34.299997、
R05 34.603422、R06 34.127486；单次差异不认定稳定收益，保留R04作控制。

下一轮独立候选：R07_BALANCED_GRID只改宏块host调度；R08_NATIVE_PACKETS只改小K输出协议。
提交包附原样R04，建议R04→R07→R04→R08→R04，用相邻控制观察波动。

- [提交包](BMMS/BMMS_V11_R07_R08_提交包.zip) / [使用说明](BMMS/BMMS_V11_R07_R08/README.md)
- [当前审计](BMMS/BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [R05/R06截图与结果](BMMS/V11_results/2026-09-26_r05_r06_submission/AUDIT.md)
- [设计](BMMS/V11_grid_packets/DESIGN.md) / [源码CPU检查](BMMS/V11_grid_packets/CHECKS.json)
- [归档SHA清单](BMMS/ARCHIVE_MANIFEST.json) / [复现说明](BMMS/README.md)

R04/R07/R08各356次普通源码CPU运行通过，3190组独立网格审计及两个故障注入检查通过。
原有3项极端数值限制保留；R07/R08本地未CANN编译或NPU测试，平台结果待反馈。
源码工作量或握手次数下降不作为设备时延预测。历史源码、ZIP和交付时状态原样保留。

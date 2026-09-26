# BatchMatmulMaxSum：R05/R06通过，推进R07/R08

R05/R06均由用户明确标注15/15 Pass，但测评有波动，未证明稳定提速。
同最新T复算：R04 34.299997、R05 34.603422、R06 34.127486；点5的T已降到1.95μs。
保留R04作对照，两个新候选分别测试核间均衡和小K输出成包，不合并R05/R06。

- [提交包：R04控制、R07、R08](BMMS_V11_R07_R08_提交包.zip) / [使用说明](BMMS_V11_R07_R08/README.md)
- [当前审计](BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [R05/R06原图和波动分析](V11_results/2026-09-26_r05_r06_submission/AUDIT.md)
- [本轮设计](V11_grid_packets/DESIGN.md) / [检查证据](V11_grid_packets/CHECKS.json)
- [原R04](BMMS_V11_R04/R04_MACRO_RING_RESIDUAL.asc) / [历史交付状态](audit_current/AUDIT_R05_R06_DELIVERY.md)

建议R04→R07→R04→R08→R04，每次整体替换官方code/kernel.asc，保存全部15点和T。
候选变化落在相邻控制的波动区间内时记为未分辨，不拼接各次最短成绩。

三版各356次普通源码CPU运行通过，两个故障注入被拒绝；3190组网格审计通过。
既有3项极端数值限制保留，本地未CANN编译/NPU测试，R07/R08仍待平台反馈。

```bash
python V11_grid_packets/build.py
python V11_grid_packets/run_checks.py
python V11_grid_packets/update_docs.py
python V11_grid_packets/package.py
```

归档：[CANN/v11](https://github.com/Pengyiyan0411/CANN/tree/v11/BMMS)。
历史文档保留交付当时状态，最新结论以当前审计和结果记录为准。

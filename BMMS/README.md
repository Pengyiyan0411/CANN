# BatchMatmulMaxSum：R11基线，R15/R16覆盖实验待测

R13/R14均15/15 Pass。同一T下R11/R13/R14为36.937232/36.854923/37.259712。
差别尚不足以排除波动，暂不合并R13/R14，保留R11。

- [提交包：R11控制、R15、R16](BMMS_V11_R15_R16_提交包.zip) / [使用说明](BMMS_V11_R15_R16/README.md)
- [当前审计](BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [R13/R14反馈及原图](V11_results/2026-09-26_r13_r14_submission/AUDIT.md)
- [设计与官方依据](V11_k_coverage/DESIGN.md) / [CPU检查](V11_k_coverage/CHECKS.json)
- [上轮交付快照](audit_current/AUDIT_R13_R14_DELIVERY.md)

R15新覆盖K=96/160/192/224；R16新覆盖K%32==16。两版独立从R11派生，
只改公开形状guard，device指令不变，保留小K和向量专用路径。先R15，再独立提交R16；
明显变化用相邻R11控制确认，不拼接最短点。

R15/R16分别628/740次普通源码CPU执行通过，314/370对重复输出核对通过。
每版1964169项K域guard枚举、两项故障注入通过；旧452次输出与冻结R11一致。
每版3项已知极端数值限制仍保留。本地无CANN/NPU验证，性能待平台反馈。

```bash
python V11_k_coverage/build.py
python V11_k_coverage/run_checks.py
python V11_k_coverage/update_docs.py
python V11_k_coverage/package.py
```

历史文件保持交付时状态，以当前审计和对应结果目录为最新结论。文档快照依赖CANN_archive。
归档：[CANN/v11](https://github.com/Pengyiyan0411/CANN/tree/v11/BMMS)。

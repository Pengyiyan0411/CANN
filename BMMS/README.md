# BatchMatmulMaxSum：V11 R01

最新决策：F01停止作为全域主线，恢复P01分支；R01重写密集输入复用。
用户确认F01截图15/15 Pass，同T21.1215分；P01历史同T32.0956分。
本轮没有测试环境，**先提交R01**。R01尚未CANN编译或NPU测试，性能待测。

- [R01提交文件](BMMS_V11_SubmitPack/R01_REUSE_2X2.asc) / [提交说明](BMMS_V11_SubmitPack/README.md)
- [R01提交包](BMMS_V11_R01_提交包.zip)
- [当前审计报告](BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [新路线设计](V11_impl/DESIGN.md) / [CPU检查](V11_impl/CHECKS.json)
- [F01已确认结果](V10_results/2026-09-26_f01_submission/AUDIT.md)
- [备用限时设备诊断](V11_impl/device_probe/README.md)

R01：153次普通源码CPU运行、4494个计划检查通过；3个已知极端数值反例保留。
CPU模型不认证CANN、真实硬件同步或性能。比赛仍只替换官方 `code/kernel.asc`。

复现离线检查：
```bash
python V11_impl/build.py
python V11_impl/run_checks.py
```

远端归档：[CANN/v11](https://github.com/Pengyiyan0411/CANN/tree/v11/BMMS)。
V9/v10分支和原始实验包不变。下游实现细节与老版结论见
[V11前完整审计](audit_current/AUDIT_BEFORE_V11.md) 和 [旧README](audit_current/README_BEFORE_V11.md)。

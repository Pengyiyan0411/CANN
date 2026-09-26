# BatchMatmulMaxSum：R08通过，推进R09/R10

用户确认R08为15/15 Pass；R07在点5运行阶段TLE，根因未确定。
按最新T5=1.90μs复算：R04 34.276579，R05 34.579701，R06 34.105836，R08 34.808289。
R08点13/14改善值得复核，仍未排除波动；暂作开发父版，历史R04保留。

- [提交包：R08控制、R09、R10](BMMS_V11_R09_R10_提交包.zip) / [使用说明](BMMS_V11_R09_R10/README.md)
- [当前审计](BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [R07/R08反馈与原图](V11_results/2026-09-26_r07_r08_submission/AUDIT.md)
- [本轮设计](V11_recovery/DESIGN.md) / [CPU检查](V11_recovery/CHECKS.json)
- [R07主机开销诊断](V11_recovery/R07_HOST_DIAGNOSIS.json) / [独立网格核对](V11_recovery/GRID_CHECKS.json)
- [上轮交付状态](audit_current/AUDIT_R07_R08_DELIVERY.md)

R09扩展残余大K的四块输出成包；R10单独验证闭式单任务网格。两版均从R08独立派生。
先R08→R09→R08，再R10→R08；每次整体替换官方code/kernel.asc，保存完整15点和T。
R10不是已经证实的TLE修复。每版444次普通CPU运行通过，仍有3项既有极端数值限制；
本地未CANN编译/NPU测试，候选待平台结果。

```bash
python V11_recovery/build.py
python V11_recovery/diagnose_r07.py
python V11_recovery/run_checks.py
python V11_recovery/update_docs.py
python V11_recovery/package.py
```

归档：[CANN/v11](https://github.com/Pengyiyan0411/CANN/tree/v11/BMMS)。
历史文档保留交付当时状态，最新结论以当前审计和结果记录为准。

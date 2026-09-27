# BatchMatmulMaxSum：R23 基线，D24 分路径诊断

R23 两轮均 15/15 Pass，Case15=15.18/15.18 μs；用户已纠正最初的 R14 标签。
保留 R14/R23 原源码，D24 只修改各实际分支的 host 计划，用于 Native、R03、Split-K 和 Case6 路径定位。
停止旧 A–C；撤回 Case7 K<512 的推断。D24 是诊断文件，不是新的冲榜版本。

- [D24 诊断包](BMMS_V11_D24_诊断包.zip)
- [提交顺序与读数](BMMS_V11_D24_Diagnostics/README.md)
- [诊断设计](V11_diagnostics24/DESIGN.md)
- [当前 R23 冲榜文件](BMMS_V11_R23/R23_SPLIT_K.asc)
- [R23 两轮通过证据](V11_results/2026-09-27_r23_submission/AUDIT.md)
- [当前审计](BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [host 检查](V11_diagnostics24/HOST_CHECKS.json)
- [CPU 计划检查](V11_diagnostics24/CPU_CHECKS.json)

```powershell
python V11_diagnostics24/build.py
python V11_diagnostics24/check_host.py
python V11_diagnostics24/check_device_plans.py
python V11_diagnostics24/update_docs.py
python V11_diagnostics24/package.py
```

本地未做 CANN/NPU 验证。历史源码、提交包和报告快照冻结。
审计快照需要历史 commit；截图已归档后不再依赖聊天附件原路径。

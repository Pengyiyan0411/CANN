# BatchMatmulMaxSum：R11工作基线，R13/R14待测

图1明确为R12、图2为R11，均15/15 Pass。R11点11为100.71μs，相对R10下降25.82%，
点10保持83.75μs。R11作为工作基线，R12不合并；本轮仅单次观测，尚无重复控制统计。
使用最新同一T复算：R10 35.553080、R11 36.937232、R12 35.618585。

- [提交包：R11控制、R13、R14](BMMS_V11_R13_R14_提交包.zip) / [使用说明](BMMS_V11_R13_R14/README.md)
- [当前审计](BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [R11/R12反馈及原图](V11_results/2026-09-26_r11_r12_submission/AUDIT.md)
- [设计](V11_flexible_grid/DESIGN.md) / [CPU检查](V11_flexible_grid/CHECKS.json)
- [独立网格审计](V11_flexible_grid/GRID_CHECKS.json) / [host微基准](V11_flexible_grid/HOST_BENCH.json)
- [上轮交付状态](audit_current/AUDIT_R11_R12_DELIVERY.md)

R13只改剩余多轮，R14只改已有单轮；均允许少量核不启动以降低最忙核工作量。
先R11→R13→R11，再R14→R11；每次整体替换官方code/kernel.asc，保留main/CMake。

三版各464次普通CPU执行、232对重复、22次隔离归约检查通过。8272组网格核对，
42次独立穷举和两项故障注入通过。既有3项极端精度限制未修复，本地无CANN/NPU验证。
R07点5运行TLE根因未知。候选未取得平台结果，不能将工作量估计当作性能保证。

```bash
python V11_flexible_grid/build.py
python V11_flexible_grid/audit_plans.py
python V11_flexible_grid/run_checks.py
python V11_flexible_grid/bench_plans.py
python V11_flexible_grid/update_docs.py
python V11_flexible_grid/package.py
```

归档：[CANN/v11](https://github.com/Pengyiyan0411/CANN/tree/v11/BMMS)。历史文件保持交付时状态，
以当前审计和对应结果目录为最新结论。update_docs.py归档历史时需要CANN_archive checkout。

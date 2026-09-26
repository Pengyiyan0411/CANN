# BatchMatmulMaxSum：R10工作基线，R11/R12待提交

用户确认R10收益稳定且明显；典型点10为84.10μs，比R08下降21.12%，15/15 Pass。
同最新T复算R10为36.170754，R08为34.805192。R09没有明显收益，不合并。

- [提交包：R10控制、R11、R12](BMMS_V11_R11_R12_提交包.zip) / [使用说明](BMMS_V11_R11_R12/README.md)
- [当前审计](BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [R09/R10反馈及原图](V11_results/2026-09-26_r09_r10_submission/AUDIT.md)
- [设计及代价](V11_single_wave/DESIGN.md) / [CPU检查](V11_single_wave/CHECKS.json)
- [网格核对](V11_single_wave/GRID_CHECKS.json) / [host微基准](V11_single_wave/HOST_BENCH.json)
- [上轮交付状态](audit_current/AUDIT_R09_R10_DELIVERY.md)

R11消除符合条件的短第二轮任务，R12独立并行N分片合并，两者都保留R10已有效的改动。
先R10→R11→R10，再R12→R10；每次只选一个asc整体替换官方code/kernel.asc。
保存全部15点与当次T，逐点比相邻控制，避免把小波动当收益。

每版452次普通CPU执行、226对重复和22次隔离归约检查通过，两个故障注入被捕获。
既有3项极端精度限制仍在；本地未CANN编译/NPU验证，候选待测。R07点5运行TLE根因未知。

```bash
python V11_single_wave/build.py
python V11_single_wave/run_checks.py
python V11_single_wave/bench_plans.py
python V11_single_wave/update_docs.py
python V11_single_wave/package.py
```

归档：[CANN/v11](https://github.com/Pengyiyan0411/CANN/tree/v11/BMMS)。历史文档保持交付时状态，
最新结论以当前审计及对应结果记录为准。update_docs.py归档历史时需要本地CANN_archive checkout。

# BatchMatmulMaxSum：保留R25，回到D24诊断

用户最新决定：R27无收益，保留R25成果，完成剩下的D24探针。本轮不交付新的优化内核。
最新图15/15 Pass，Case5/13/14为6.90/17.77/14.24 μs；按交付上下文归属R27，平台源码hash未核验。
R26、R27均不作为升级。所有旧源码和提交包保持冻结。

- [R25保留版](BMMS/BMMS_V11_R25/R25_NATIVE_TARGETED.asc)
- [D24续跑包](BMMS/BMMS_V11_D24_续跑包.zip)
- [续跑顺序及解码说明](BMMS/BMMS_V11_D24_Resume/README.md)
- [原D24完整包](BMMS/BMMS_V11_D24_诊断包.zip)
- [N01–N05已完成结果](BMMS/V11_results/2026-09-27_d24_native/AUDIT.md)
- [R27最新否定结果](BMMS/V11_results/2026-09-27_r27_observed/AUDIT.md)
- [当前审计](BMMS/BatchMatmulMaxSum_当前审计报告_2026-09-26.md)

冲榜基线R25与诊断基线R23分开保留。D24内Case5回到旧耗时不代表R25成果丢失。
N01–N05无需重跑。先C01→R7_01–05，再L00→L05；剩余L和Case6按结果展开。
原D24代码未改，续跑包仅重组已有文件；没有新增CANN/NPU或性能验证。

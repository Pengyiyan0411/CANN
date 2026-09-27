# BatchMatmulMaxSum：保留 R25，R01–R31 阶段总结

2026-09-27。最新用户反馈：**R29 无收益，R30/R31 导致其他点退化**。三版均不晋升，继续冻结完整 R25；R26/R27/R28 也未晋升。本轮只整理文档和结果，没有修改内核。

- [详细阶段总结：版本演进、逐点证据、探针推导、完整成绩和后续方向](BMMS/BMMS_阶段进度总结_R01-R31_20260927.md)
- [当前性能源码 R25_NATIVE_TARGETED](BMMS/BMMS_V11_R25/R25_NATIVE_TARGETED.asc)
- [R29–R31 最新反馈](BMMS/V11_results/2026-09-27_r29_r30_r31_feedback/AUDIT.md)
- [当前诊断进度](BMMS/V11_results/2026-09-27_r29_r30_r31_feedback/PROGRESS.json)
- [当前审计](BMMS/BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [原 D24 续跑说明](BMMS/BMMS_V11_D24_Resume/README.md)

R25 保留 R23 的 Case15 Split-K 和 Case5 的小输出消费策略。D24 仍基于原 R23，已完成 15 个诊断提交；不能把诊断时 Case5 回到约 7 μs 误判为 R25 优势丢失。

R29–R31 此次只有定性反馈，退化点编号、幅度、完整 Pass 数和重复次数未知。历史模型检查不等于硬件收益。原源码、交付包、截图和报告保持原字节；旧文档中的待测建议属于历史快照，以当前总结为准。

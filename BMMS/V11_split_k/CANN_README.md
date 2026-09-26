# BatchMatmulMaxSum：R14 基线，R23 小输出长 K 并行

R23 依据真实 B/M/N/K、dtype/布局和核数选择 Cube Split-K；各段求和成完整 C 后才做 max(N)/sum(M)。
未命中条件仍走 R14。附单分片对照和四个几何探针。本地源码模型检查通过，CANN/NPU 验证待提交。

- [R23 单文件](BMMS/BMMS_V11_R23/R23_SPLIT_K.asc)
- [提交包](BMMS/BMMS_V11_R23_提交包.zip)
- [提交与消融说明](BMMS/BMMS_V11_R23/README.md)
- [当前审计](BMMS/BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [Split-K 设计](BMMS/V11_split_k/DESIGN.md)
- [源码检查](BMMS/V11_split_k/CHECKS.json)
- [分派检查](BMMS/V11_split_k/DISPATCH_CHECKS.json)
- [Case15 新证据](BMMS/V11_results/2026-09-27_case15_long_k/AUDIT.md)
- [上轮快照](BMMS/audit_current/AUDIT_R22_DELIVERY.md)

```powershell
cd BMMS
python V11_split_k/build.py
python V11_split_k/run_checks.py --resume
python V11_split_k/check_dispatch.py
python V11_split_k/update_docs.py
python V11_split_k/package.py
```

R22 收到定性无收益反馈；R20 编译失败且无日志。旧源码、结果、提交包保持冻结。
审计快照生成需要 CANN_archive 中的历史 commit。

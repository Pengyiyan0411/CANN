# BatchMatmulMaxSum：R14 基线，R22 按元数据选择固定内核

R20 平台编译失败且没有日志。R22 从 R14 重做：短 N 窄列、短 M 宽列、对齐稠密高 M 块；
host 根据真实形状、K、dtype、布局和并行度选择内核。单文件提交，未覆盖组合保留 R14。
本地源码模型检查通过，CANN 编译/NPU 性能待提交，R14 仍是已验证基线。

- [R22 单文件](BMMS/BMMS_V11_R22/R22_SHAPE_SWITCH.asc)
- [提交包](BMMS/BMMS_V11_R22_提交包.zip)
- [使用说明](BMMS/BMMS_V11_R22/README.md)
- [当前审计](BMMS/BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [分派设计](BMMS/V11_shape_dispatch/DESIGN.md)
- [源码检查](BMMS/V11_shape_dispatch/CHECKS.json)
- [分派检查](BMMS/V11_shape_dispatch/DISPATCH_CHECKS.json)
- [R20 失败反馈](BMMS/V11_results/2026-09-27_r20_compile_failed/AUDIT.md)
- [上轮交付快照](BMMS/audit_current/AUDIT_R20_R21_DELIVERY.md)

```powershell
cd BMMS
python V11_shape_dispatch/build.py
python V11_shape_dispatch/run_checks.py
python V11_shape_dispatch/check_dispatch.py
python V11_shape_dispatch/update_docs.py
python V11_shape_dispatch/package.py
```

旧源码、结果和提交包保持冻结。审计快照生成需要 CANN_archive 中的历史 commit。

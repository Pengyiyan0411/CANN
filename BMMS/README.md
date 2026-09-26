# BatchMatmulMaxSum：R14 基线，Native small-K R20/R21

本轮根据用户的 Case 5 Native-stress 响应，针对原生 K32/64/128 路径实现独立候选。
R14 仍是工作基线；R20/R21 暂无平台结果，历史后续版本无收益反馈未被写成定量成绩。

- [R20/R21 提交包](BMMS_V11_R20_R21_提交包.zip) / [使用说明](BMMS_V11_R20_R21/README.md)
- [当前审计](BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [专项设计](V11_native_specialize/DESIGN.md) / [源码检查](V11_native_specialize/CHECKS.json)
- [Case 5 诊断证据](V11_results/2026-09-27_native_case5/AUDIT.md)
- [上轮交付快照](audit_current/AUDIT_R17_R18_R19_DELIVERY.md)

先独立提交 R21（L0 搬运复用），再提交 R20（宽 N MMAD）。R14 控制源码已随包提供。
普通离线源码模型输出与 R14 一致；本地无 CANN/NPU，不宣称真实性能收益。

```powershell
python V11_native_specialize/build.py
python V11_native_specialize/run_checks.py
python V11_native_specialize/check_dispatch.py
python V11_native_specialize/update_docs.py
python V11_native_specialize/package.py
```

源码与历史记录归档：[CANN/v11](https://github.com/Pengyiyan0411/CANN/tree/v11/BMMS)。
审计快照生成依赖本地 CANN_archive 中的历史 commit。

# BatchMatmulMaxSum：R01反馈后提交R02/R03

R01已获用户明确标注的15/15 Pass。同T复算31.8536，P01历史32.0956。
点9–11有改善，点12回退抵消大部分收益。用户无测试环境，本轮继续平台提交。

1. [R02_MACRO_RING.asc](BMMS_V11_R02_R03/R02_MACRO_RING.asc)：减少宏块输出同步。
2. [R03_RESIDUAL_DENSE.asc](BMMS_V11_R02_R03/R03_RESIDUAL_DENSE.asc)：保留原R01，补公开shape差集。

两版独立，不要拼接；每次只替换官方 `code/kernel.asc`。
[提交包](BMMS_V11_R02_R03_提交包.zip) / [提交说明](BMMS_V11_R02_R03/README.md)。

- [当前审计](BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [R01结果和逐点分数](V11_results/2026-09-26_r01_submission/AUDIT.md)
- [新实验设计](V11_followup/DESIGN.md) / [检查记录](V11_followup/CHECKS.json)
- [冻结R01源码](BMMS_V11_SubmitPack/R01_REUSE_2X2.asc)
- [F01历史反馈](V10_results/2026-09-26_f01_submission/AUDIT.md)

新候选每版169次普通源码CPU运行通过，所测输出与R01逐位一致；3个极端数值限制保留。
本地无CANN/NPU，不能把CPU模型通过称为设备通过或提速。平台结果待返回。

```bash
python V11_followup/build.py
python V11_followup/run_checks.py
python V11_followup/package.py
```

归档：[CANN/v11](https://github.com/Pengyiyan0411/CANN/tree/v11/BMMS)。
R01交付时点的说明见 [历史快照](audit_current/AUDIT_R01_DELIVERY.md)。

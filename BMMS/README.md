# BatchMatmulMaxSum：R04反馈后推进R05/R06

本轮截图15/15 Pass，按唯一前序交付归属R04，同最新T复算34.4965，
当前记录内最好。R04同时保留R02大点及R03点15的收益，继续冻结为保底。

两份独立候选已准备好：先提交 [R06_MACRO_MMAD.asc](BMMS_V11_R05_R06/R06_MACRO_MMAD.asc)，
再提交 [R05_DEFERRED_MAX.asc](BMMS_V11_R05_R06/R05_DEFERRED_MAX.asc)。前者合并整宏块
Cube指令和L0搬运，后者复用N方向lane max并减少完整C块清填；每次整体替换官方`code/kernel.asc`。

- [提交包](BMMS_V11_R05_R06_提交包.zip) / [使用说明](BMMS_V11_R05_R06/README.md)
- [当前审计](BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [R04截图与同T结果](V11_results/2026-09-26_r04_submission/AUDIT.md)
- [本轮设计](V11_lowlevel/DESIGN.md) / [源码CPU检查](V11_lowlevel/CHECKS.json)
- [冻结R04源码](BMMS_V11_R04/R04_MACRO_RING_RESIDUAL.asc) / [历史交付快照](audit_current/AUDIT_R04_DELIVERY.md)

三版各256次普通源码CPU运行通过，普通输出记录逐位一致，两个负向检查被正确拒绝。
原有3个极端数值限制保留；未CANN编译/未运行NPU，R05/R06实际成绩待平台反馈。
模型中的指令调用减少不代表同倍数提速。用户暂无环境，继续平台提交。

```bash
python V11_lowlevel/build.py
python V11_lowlevel/run_checks.py
python V11_lowlevel/update_docs.py
python V11_lowlevel/package.py
```

归档：[CANN/v11](https://github.com/Pengyiyan0411/CANN/tree/v11/BMMS)。
历史交付文档保留当时状态，最新结论以当前审计及结果记录为准。

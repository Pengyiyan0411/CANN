# BatchMatmulMaxSum：按计划以R14为基线，交付R17/R18/R19

R14已有15/15 Pass、同当前T复算37.259712分。用户计划指定R14为开发起点；
相对R11的0.322480分仍未排除波动，没有新的NPU性能结论。

- [提交包：R14控制与三个独立候选](BMMS_V11_R17_R18_R19_提交包.zip) / [使用说明](BMMS_V11_R17_R18_R19/README.md)
- [当前审计](BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [用户计划快照](V11_a_resident/INPUT_PLAN.md) / [实现设计](V11_a_resident/DESIGN.md)
- [CPU检查](V11_a_resident/CHECKS.json) / [上轮交付快照](audit_current/AUDIT_R15_R16_DELIVERY.md)

R17/R18分别迁移已有两项K覆盖修改，保留R14网格。R19独立实现K256/512的完整A跨N驻留，
保留MMAD顺序、FP32 ring和消费者。按R17→R18→R19提交，各自用R14控制，不预先合并。
四N宏块合成样例中A读取减少75%、总输入读取减少25%；这只表示源码逻辑流量减少。
普通离线用例通过，3项已知极端数值限制仍保留；无本地CANN/NPU验证，实际收益待提交。

```bash
python V11_a_resident/build.py
python V11_a_resident/run_checks.py
python V11_a_resident/update_docs.py
python V11_a_resident/package.py
```

历史源码与结果保持冻结，以当前审计为最新工作状态。原计划已有INPUT_PLAN.md冻结副本，
文档快照依赖CANN_archive。归档：[CANN/v11](https://github.com/Pengyiyan0411/CANN/tree/v11/BMMS)。

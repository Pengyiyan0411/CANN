# BatchMatmulMaxSum：R02/R03反馈后提交R04

R02、R03均由用户确认15/15 Pass。同最新T复算：R02 33.7734，
R03 33.3163，R01 31.8368，P01历史32.0879。
R02改善点9–12；R03点15降至37.08μs，点7也改善。

下一次提交 [R04_MACRO_RING_RESIDUAL.asc](BMMS_V11_R04/R04_MACRO_RING_RESIDUAL.asc)：
合并上述两项，不叠加新调参。整体替换官方`code/kernel.asc`。
[提交包](BMMS_V11_R04_提交包.zip) / [提交说明](BMMS_V11_R04/README.md)。

- [当前审计](BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [R02/R03原图、逐点耗时及同T得分](V11_results/2026-09-26_r02_r03_submission/AUDIT.md)
- [R04设计](V11_merge/DESIGN.md) / [CPU检查证据](V11_merge/CHECKS.json)
- [冻结R02/R03](BMMS_V11_R02_R03/README.md) / [R01结果](V11_results/2026-09-26_r01_submission/AUDIT.md)

R04本地173次普通源码CPU运行通过，已知3个极端数值限制保留。
未CANN编译/未运行NPU；父版本Pass不代表R04已通过。用户暂无环境，继续平台提交。

```bash
python V11_merge/build.py
python V11_merge/run_checks.py
python V11_merge/update_docs.py
python V11_merge/package.py
```

归档：[CANN/v11](https://github.com/Pengyiyan0411/CANN/tree/v11/BMMS)。
历史交付文档保留当时状态，最新结论以当前审计及结果记录为准。

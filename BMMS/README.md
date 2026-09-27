# BatchMatmulMaxSum：R23 基线，R25 Native 三点特化候选

N01–N05 五份均15/15，通过同批阳性校准定位 Case5/13/14 均为 K128。
Case5 是多 batch 小输出，13/14 是单 batch 且 M/N>32。R25 仅优化这两类原 Native 输入。
先验收完整15点与非目标退化，再推进其他点。R23 仍是已验证基线；不再要求额外 shape probes。

- [首选完整提交文件](BMMS_V11_R25/R25_NATIVE_TARGETED.asc)
- [R25 提交包](BMMS_V11_R25_提交包.zip)
- [提交与回退说明](BMMS_V11_R25/README.md)
- [设计和验证边界](V11_native_targeted25/DESIGN.md)
- [N01–N05 原始结果](V11_results/2026-09-27_d24_native/AUDIT.md)
- [当前审计](BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [冻结 R23](BMMS_V11_R23/R23_SPLIT_K.asc)

```powershell
python V11_native_targeted25/build.py
python V11_native_targeted25/run_checks.py
python V11_native_targeted25/check_host.py
python V11_native_targeted25/check_bounds.py
python V11_native_targeted25/record_results.py
python V11_native_targeted25/update_docs.py
python V11_native_targeted25/package.py
```

本地 CPU/host 检查通过，未做 CANN/NPU 验证。R25 平台结果待回传；历史源码、提交包、审计快照保留。

# R27_DENSE_UNITFLAG 提交说明

先提交 `R27_DENSE_UNITFLAG.asc`：完整单文件，无需拼接。
`CONTROL_R25.asc` 与冻结的 `R25_NATIVE_TARGETED.asc` 逐字相同，可作回退或相邻对照。
不要再把R26作为默认升级；最新图13/14没有收益证据。

R27保留R25的Case5路径、消费者、分核和分配；仅在Native单batch K128且M/N>32、blocks>1时更换Cube同步。
UnitFlag替换MMAD→FIX整块等待，尾块依赖和所有槽位复用保护保留。
没有合入R26的packet读取，没有更改其他测试点策略。

本地通过实际C++源码CPU模型和host对照；尚未CANN编译或NPU运行，不保证平台提速。

验收顺序：

1. 全部15点Pass；若编译失败、错误或运行超时，立即回退CONTROL_R25。
2. 查看13/14是否明显且可重复下降，同时核对5、15和其余点。
3. 仍只有小幅变化时，必要时用包内R25做相邻对照；无稳定收益则保留R25。

只需先验证这个候选，不继续旧探针，不申请额外算力。
源码SHA256在MANIFEST.json。CPU_CHECKS/HOST_CHECKS保存绑定源码的结果与验证边界。
详细审阅和API依据在DESIGN.md。CPU逐位一致不等同于设备编译后的逐位一致。

在完整归档仓库内复现：

```powershell
python V11_native_unit27/build.py
python V11_native_unit27/check_host.py
python V11_native_unit27/run_checks.py
python V11_native_unit27/update_docs.py
python V11_native_unit27/package.py
```

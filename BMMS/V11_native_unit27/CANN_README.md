# BatchMatmulMaxSum：R26不升级，R25保留，R27单独验证Cube同步

最新截图按交付上下文归为R26：15/15 Pass，Case13/14为17.26/13.77 μs，没有收益证据。
Case5为6.86 μs，高于R25的6.60/6.45 μs；没有把这个变化直接解释成噪声。
R25继续作为工作基线。R27只替换原Native、B1/K128/M,N>32/blocks>1的MMAD→FIX同步方式。
Case5和R25所有消费者保留；R26 packet消费者不携带。尚无R27设备性能结果。

- [R27完整提交源码](BMMS/BMMS_V11_R27/R27_DENSE_UNITFLAG.asc)
- [R27提交包，含原字节R25对照](BMMS/BMMS_V11_R27_提交包.zip)
- [验证顺序和边界](BMMS/BMMS_V11_R27/README.md)
- [重新审阅、同步说明及API依据](BMMS/V11_native_unit27/DESIGN.md)
- [最新截图与否定结果归档](BMMS/V11_results/2026-09-27_r26_observed/AUDIT.md)
- [当前审计报告](BMMS/BatchMatmulMaxSum_当前审计报告_2026-09-26.md)

源码模型与host分派检查通过；没有本地CANN编译、NPU运行或性能提升证明。
本轮只提交一个候选，必须先检查全部15点，再验13/14可重复下降和5保持。
若无收益即回退R25；旧源码、截图、ZIP保持冻结。

```powershell
cd BMMS
python V11_native_unit27/build.py
python V11_native_unit27/check_host.py
python V11_native_unit27/run_checks.py
python V11_native_unit27/record_results.py
python V11_native_unit27/update_docs.py
python V11_native_unit27/package.py
```

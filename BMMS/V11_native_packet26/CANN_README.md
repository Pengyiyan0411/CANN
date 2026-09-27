# BatchMatmulMaxSum：R25 Case5 冻结，R26 仅调整单 batch Native 消费策略

最新两图均15/15，Case5为6.60/6.45 μs，Case13为16.80/16.91 μs，Case14为13.84/13.63 μs。
按上一轮首选交付暂归属 R25，用户未再次确认文件名，平台源hash未知。
R26 从完整 R25 派生：保留 Case5 内核和路由，只替换 Native B1/K128/M,N>32/blocks>1 的消费者。

- [R26 完整提交文件](BMMS/BMMS_V11_R26/R26_DENSE_PACKET.asc)
- [R26 提交包，含冻结 R25 对照](BMMS/BMMS_V11_R26_提交包.zip)
- [提交顺序与验证边界](BMMS/BMMS_V11_R26/README.md)
- [设计和源码证据](BMMS/V11_native_packet26/DESIGN.md)
- [本轮截图归档](BMMS/V11_results/2026-09-27_r25_observed/AUDIT.md)
- [当前审计](BMMS/BatchMatmulMaxSum_当前审计报告_2026-09-26.md)

本地源码/host/边界检查通过，未做 CANN/NPU 编译运行。R26 平台结果待回传。
先验证13/14收益、Case5保持以及全部15点，再推进其他点。旧提交源码与ZIP保持冻结。

```powershell
cd BMMS
python V11_native_packet26/build.py
python V11_native_packet26/run_checks.py
python V11_native_packet26/check_host.py
python V11_native_packet26/check_bounds.py
python V11_native_packet26/record_results.py
python V11_native_packet26/update_docs.py
python V11_native_packet26/package.py
```

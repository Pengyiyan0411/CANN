# CANN

BatchMatmulMaxSum 算子开发归档。当前用户精简方案实现位于 `v10` 分支，V9 的源码和平台结果保留在 `v9` 分支；此前版本保留在各历史分支。

## 当前交付：V10

- [F01_STREAM_M.asc](BMMS/BMMS_V10_SubmitPack/F01_STREAM_M.asc)：Batch / Split-M 流式融合。
- [F02_STREAM_MN.asc](BMMS/BMMS_V10_SubmitPack/F02_STREAM_MN.asc)：只增加选择性 Split-N。
- [提交包](BMMS/BMMS_V10_提交包.zip)、[使用说明](BMMS/BMMS_V10_SubmitPack/README.md)、[设计](BMMS/V10_impl/DESIGN.md)、[检查证据](BMMS/V10_impl/CHECKS.json)。

两份文件都整体替换官方 `code/kernel.asc`。每版512次正常源码CPU模型运行和8190个planner检查通过；已有3个极端数值反例保留。尚未CANN编译或运行NPU，不能承诺平台Pass或加速。先提交F01，再提交F02；第三轮等真实结果后做定向优化。

P01已有局部输出接口，本轮不是首次移除完整C分配。SDK局部输出可能经GM暂存；V10实际改变调度、partialY归约和尾块处理。D04保留旧路线对照。

## 当前结果

用户返回的 D01、S01、D02 均为15/15 Pass。按截图最新同一组 T 复算：

| 版本 | 分数 | 状态 |
|---|---:|---|
| P01历史耗时 | 32.0956 | 对照，非同轮复测 |
| D01 Dense K128 | 28.2532 | 点15约2.94倍加速，点10–12大幅退化 |
| S01 Small NT | 31.7913 | 尚无明确整体收益 |
| D02 Dense K64 | 26.8647 | 点9–11/15比D01更慢，点12基本不变 |
| D03（截图身份推定） | 28.4493 | 未恢复主要退化，15/15 Pass |

T的点5、13、14已经更新，不能直接与旧34.0599分比较。完整原始图、逐点耗时和得分贡献见 [首轮结果审计](BMMS/V9_results/2026-09-26_first_submission/AUDIT.md)。源身份由用户文件名确认，未提供平台源码hash或提交编号。

最新未标注截图紧接D03交付，先按D03分析，**不是用户明确标注**。见 [D03后续截图审计](BMMS/V9_results/2026-09-26_d03_submission/AUDIT.md)。停止缩小K和C槽数扫描，P01保底，暂缓M01组合。

保留对照 [D04_DENSE_M128_N128.asc](BMMS/BMMS_V9_D04/D04_DENSE_M128_N128.asc)：增大M块以复用B，同时调整producer/consumer与小块同步。D03/D04各283次源码CPU模型检查通过；一个公开控制例的逻辑输入读量减少1/3，非性能预测。D04尚未CANN编译或上卡，详见 [D04说明](BMMS/BMMS_V9_D04/README.md)。

## 源码与证据

- [单文件候选与提交说明](BMMS/BMMS_V9_SubmitPack/README_提交顺序.md)：保留原交付时点说明，最新状态以首轮结果审计为准。
- [原始提交实验包](BMMS/BMMS_V9_提交实验包.zip)：历史包保持原字节，包含 D01/D02/S01/M01 与 P01 对照。
- [实现状态](BMMS/V9_impl/IMPLEMENTATION_STATUS.md)、[路线设计](BMMS/BatchMatmulMaxSum_V9_冲榜路线设计.md)。
- [数值边界审查](BMMS/V9_impl/precision_review.md)：平台15点通过没有排除强消减和BF16中间溢出反例。
- [离线检查结果](BMMS/V9_impl/cpu_checks.json)：496次源码CPU模型检查，不能代替设备全域验证。
- [归档清单](BMMS/ARCHIVE_MANIFEST.json)：文件字节数及SHA256；不含编译器二进制、缓存或外部CATLASS源码。

## 本地复现

Python 3、NumPy 用于数学模型；源码模型另外需要支持 C++20 的 g++，可用 `CXX` 指定。下列命令不申请或使用NPU：

```sh
python BMMS/V9_impl/ingest_first_results.py
python BMMS/V9_impl/ingest_d02_results.py
python BMMS/V9_impl/ingest_d03_results.py
python BMMS/V9_impl/validate_package.py
python BMMS/V9_impl/test_semantics.py
python BMMS/V9_impl/run_checks.py
python BMMS/V9_impl/run_d03_checks.py
python BMMS/V9_impl/run_d04_checks.py
python BMMS/V10_impl/build.py
python BMMS/V10_impl/run_checks.py
python BMMS/V10_impl/package.py
```

数学审查脚本退出0表示普通断言与已知失败均被正确复现，`candidate_precision_accepted=false`仍保留。重新运行会更新对应本地检查产物；原平台截图与提交源不应修改。

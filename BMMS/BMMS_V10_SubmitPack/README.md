# V10 流式融合提交包

已按用户提供的精简方案实现，重新编号为 V10。两份 `.asc` 都是完整、独立的提交文件，**整体替换官方 `code/kernel.asc`**，保留官方 main / CMake；使用默认 SDK MIX 编译模式。

| 顺序 | 文件 | 唯一策略差异 |
|---|---|---|
| 先提交 | `F01_STREAM_M.asc` | Batch / Split-M 流式融合，不拆 N |
| 再提交 | `F02_STREAM_MN.asc` | B/M 并行不足且 N≥1024 时允许 Split-N |

先分别取得 15 点 Pass/耗时，再比较。提交结果请保留 F01/F02 标记；当前没有实测证据支持选定其中一份作为更快版本。D04 保留为旧路线对照，不混入本轮代码。

## 实际实现

同一个 Matmul 内核覆盖 FP16/BF16、NN/NT/TN/TT 和任意合法尾块。默认 M64/N128，完整 K 以 FP32 累加，每块输出后立即更新 rowMax；处理完 N 后才 Sum。没有 Split-K、Tiny、Skinny 或 P01 回退路由。

主路径每个 M 分片输出一个 FP32 partialY（物理槽按 64 字节隔离写入）；Split-N 输出 partialMax，最终逐行 Max 后再 Sum。最后的小归约放在同一次 MIX launch 中完成。

应用没有完整 C 工作区。**Atlas A2 的局部输出接口可能经 SDK GM 暂存，不代表已消除所有 C 的 GM 搬运。** P01 原来就有此接口；本版的可验证变化是调度、生命周期、partialY 和尾块处理，性能增益尚未测得。

## 验证状态

每份候选：512 次正常源码 CPU 模型运行、256 对逐位重复检查、8,190 个 planner 检查通过。覆盖双 dtype×四布局、全负、跨 N shard 的不同获胜列、M/N/K 尾块、K8192、M8192、B64、多任务循环。F02 有 160 次运行进入 Split-N。两版本在本组有限测试上的输出逐位一致。

正常用例最大绝对误差约 `4.77e-7`，最大相对误差约 `9.25e-7`，oracle 对实际 FP16/BF16 储值以 FP64 完成三阶段计算，最后转 FP32。用例为有界数据，结果不是全数值域保证。

模型仍复现每版 3 个已知精度限制：FP16/BF16 强相消各 1 个，BF16 中间溢出 1 个。`full_domain_precision_accepted=false`。这些失败有保留，没有通过放宽容差隐藏。

**尚未 CANN 编译或上 NPU，不能把 CPU 模型通过当作平台通过或性能提升。** SDK tiler 的实际返回、比赛安装版的尾块输出约定、KFC/硬件同步及耗时仍须提交验证。新路线取消小 shape 专用分支，小测试点可能退化。

## 后续只做一轮定向优化

当前无需先申请卡时，可先提交 F01/F02。若均通过但仍大幅落后，或出现仅靠截图无法定位的失败，再用一次短设备窗口检查最差 3–5 个 shape：实编、尾块精度、msprof。根据证据再从 64×256 / 128×128 或缓冲重叠中选一项，不预先制造第三个“优化版”。

源码、构建脚本和设计在仓库 `BMMS/V10_impl`，离线复现：

```sh
python BMMS/V10_impl/build.py
python BMMS/V10_impl/run_checks.py
python BMMS/V10_impl/package.py
```

支持 C++20 的 g++ 和 Python 3 即可运行这些离线步骤。`MANIFEST.json` 绑定源码 SHA256，`CPU_CHECKS.json` 明确区分正常测试与已知限制。

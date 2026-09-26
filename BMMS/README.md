# BatchMatmulMaxSum V7.1：按模块合并 V7 与 V4.3

> 当前任务更新：已按用户精简方案实现 [V10 F01/F02](BMMS_V10_SubmitPack/README.md)，源码与可复现检查见 [V10设计](V10_impl/DESIGN.md)。每版512次正常源码CPU运行、8190个调度检查通过；3个已知极端精度反例保留，尚未CANN编译/上卡。D04保留对照。远端登录已恢复，V9已推送到CANN/v9，V10归档到CANN/v10。下方均为历史快照。

> 当前入口：最新截图暂按D03分析，同T约28.4493，主要退化未恢复。下一份为增加B复用的 [D04](BMMS_V9_D04/README.md)，已完成CPU源码检查、待平台验证。见 [本轮审计](V9_results/2026-09-26_d03_submission/AUDIT.md)。下文各版本保留为历史记录。

> 最新平台反馈：D02为15/15 Pass，但同T复算26.8647，低于D01。下一份为K128双L0C的 [D03](BMMS_V9_D03/README.md)，目前仅完成CPU源码模型检查；详见 [D02审计](V9_results/2026-09-26_d02_submission/AUDIT.md)。后续代码归档至 [CANN](https://github.com/Pengyiyan0411/CANN)，远端登录问题尚待解决。以下为历史记录。

> 最新进度（2026-09-26）：V9 已实现四份独立提交实验文件，见 [提交顺序](BMMS_V9_SubmitPack/README_提交顺序.md)、[实验包](BMMS_V9_提交实验包.zip) 和 [实现状态](V9_impl/IMPLEMENTATION_STATUS.md)。已完成离线源码模型检查，尚未 CANN 编译或 NPU 验证，已知数值反例仍保留。以下 V7.1 内容为历史记录。

## 交付物与状态

`code/kernel.asc` 是本次候选替换文件。仍只替换官方工程的 `code/kernel.asc`，不改官方 main、CMake 或目录结构。本 ZIP 是源码/检查包，不是可原样上传的完整官方模板。

用户截图确认 V4.3、V7 各自曾 15/15；本次新合并版本尚未在 Bisheng/CANN 9.0/Atlas A2 上编译运行。CPU 适配器不是 NPU 仿真器。`reports/semantics.json` 保留独立精度门槛警告，不能把本次测试描述为“所有精度标准全部通过”。

## 这次选择了什么

| 输入家族（有优先顺序） | 新版实现来源 |
|---|---|
| M=N=1 | V4.3 Dot，函数体不变 |
| 原 Tiny 条件 | V4.3 Tiny，函数体不变 |
| V7 Resident 条件 | V7 Resident，函数体和阈值不变 |
| N=1 且 A 按 [M,K] 连续存储；或 M=1 且 B 按 [N,K] 连续存储 | V7 Skinny，函数体、完整 K 点积和规划不变 |
| 其余合法输入 | V4.3 Fast/显式 GM-stripe 与原规划器；有两处明确安全修正 |

Resident 条件：M≤32、N≤64、K≤128、MN≤256、MNK≤16384、(M+N)K≤8192。Tiny 优先于 Resident，均优先于 Skinny。这与 V7 的选择顺序相同。

**这不是按隐藏测试编号取两份成绩的最小值。** 代码不识别点 3、8 或 15，不读取评测文件，不复用答案。它只读取合法的 shape、dtype、layout 和可用核数；Matmul fallback 另外使用返回的 tiling 元数据。

## 为什么没有把整个 V7 面板实现一起放进来

V7 的 panel 路径是 AIC 本地 Matmul，需要在包含头文件前定义 `ASCENDC_CUBE_ONLY`。V4.3 是默认 MIX/KFC Matmul。C++ namespace 不能隔离这个预处理选择，运行时 if 也不能切换它。

本版只移植 V7 中没有 Matmul 对象的 Resident/Skinny 模块，保留 V4.3 的默认 MIX 编译模式。因此没有重新定义 SDK 私有别名、重置头文件保护宏、或将两套不兼容注册宏混合使用。V7 的 PanelProducer/PanelConsumer 不在提交文件中。

代价是：V7 的部分改善可能来自 panel 而非两个 Vector 专用路径；截图没有提供各点 shape 或实际分支，不能保证所有 V7 优势点逐个保留。该限制比新增未经验证的双模式 SDK 适配更可控。

## 两处安全修正

1. V4.3 的 Fast 消费者仍假定全分片 N 外层、M 内层。新增 `FlatFastStream` 检查实际返回的 Norm tiling：仅一维有多个块，或 ORDER_N 且 stepM 覆盖完整 M 分片时才允许进入旧 Fast；否则转原 Safe。生产代码没有增加第二次 launch。
2. Fast 路径把非队列 running buffer 写入 partialMax 后，增加 `MTE3_V` fence，防止下一任务提前覆盖它。没有更改数学计算。

这两项也意味着不能保证一般路径在每个形状都逐指令复刻旧 V4.3 的耗时，尤其某个 Fast tiling 被安全门拒绝时。

## 截图结果的正确解释

按相同 T 值及题面公式，V4.3 约 31.1967 分，V7 约 30.6206 分。V7 7 点更快、8 点更慢。两张截图逐点取较小耗时得到约 35.0815 分，这是**已有两张截图的理想拼接参照**，不是 V7.1 实测成绩、保证值或全局性能上限。

详细逐点表在 `reports/screenshot_table.md`；复算代码为 `tools/screenshot_scores.py`。

## 可重跑 CPU 检查

```bash
bash tests/run_all.sh
```

需要 C++20 编译器和 Python 3。脚本直接从提交源码抽取函数；运行耗时随 CPU 而变。检查结果不能代替 CANN 编译、KFC/缓存时序验证或 Judge。先阅读 `AUDIT.md` 中精度警告。

## 本地真机对照（不改官方工程）

```bash
bash tools/build_device.sh reference/kernel_v4_3.asc device_v43
bash tools/build_device.sh reference/kernel_v7.asc device_v7
bash tools/build_device.sh code/kernel.asc device_hybrid
```

随后用 `tools/device_check.py` 对三份可执行文件分别生成/执行同一套确定性用例。`--cores` 必须填实际可用 AIC 数，不要默认 24。例子：

```bash
python3 tools/device_check.py --exe device_hybrid/cmake/bench --cores 20 --out results_hybrid --repeats 10
```

脚本始终分别记录独立绝对误差、相对误差、组合容差和位模式一致性；默认按独立阈值判定。不要为了让测试绿灯而忽略其警告。上述用例是自建的，非官方隐藏 15 点。

`results_hybrid/profile.sh` 是生成的 profiling 命令，按需在设备执行，然后：

```bash
python3 tools/profile_summary.py results_hybrid --contains bmms --output hybrid_profile.json
```

过滤串应为 `bmms`，不能只选 `bmms7`，否则会漏掉继承的 `bmms43_*` 通用路径。以 Task Duration 比较，不要把 Host 调用时间当作 Judge 用时。多个 kernel/task type 被分别保留，脚本不会把它们随意相加。

`tools/compare_profiles.py` 可按输入 SHA-256、shape、dtype、layout 和核数对齐两份真实结果；正确性未通过、测量缺失或类型不明确时不计算加速比。

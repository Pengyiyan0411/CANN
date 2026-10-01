# R46：Case8 主体 fast + 完整尾部分片

2026-09-28。提交文件为 `R46_CASE8_FAST_MAIN_TAIL.asc`，完整单文件，直接基于冻结 R43。R43 是目前对照；R46 是待平台验证的候选。

| 版本 | Case8，μs | 当前判断 |
|---|---:|---|
| R25 | 约 91 | 历史值 |
| R43 PADDED_MACRO | 62.45 | 用户确认明显收益，其他点变化在波动范围内 |
| R45 PACK_TAIL_ZERO | 62.54、62.47 | 无可见收益，不合并 |
| R46 FAST_MAIN_TAIL | 待测 | 本次候选 |

## 从报告中采用的方向

采用 `一个不一定可靠的诊断report.md` 对 Case8 的建议：把不对齐 N 从 fast 路径的全局拒绝条件，改成局部尾部处理问题。原始探针源码与全部结果不在这份报告里，因此没有把报告的其他 case 结论覆盖进已有档案，也没有假定 Case8 的精确 M/N/K。

新入口只在原 R43 `Eligible` 成立且 `N % 16 != 0` 时尝试：B=1；M、N 在 [1024,2048)；1024<K<1280 且 K%8=0；FP16/BF16。没有再要求 M%16!=0 或 K%32!=0。所有策略依据输入元数据；不读取输入值决定路由，不使用测试点编号。

## 最终实现

R46 直接读取原始 A/B，通过现有 SDK Matmul 的 VECIN 消费接口计算。没有 R43 的整份 A/B 补齐 workspace、预处理拷贝和 pack 阶段屏障。SDK 内部仍可能经过 GM 暂存，不能据此声称硬件直接从 L0C 输出到 UB，或完全消除了 C 的 GM 流量。

设每个 C tile 的完整列宽为 `V`，规划用的虚拟列数为：

```text
virtualN = ceil(N / V) * V
delta = virtualN - N             // 1 <= delta < V
```

把这些完整 tile 均衡分到至少两个 N 分片。普通分片使用其原始列起点。最后一个分片整体左移 `delta`，使它恰好结束在真实 N：

```text
firstTile = floor(ns * nTiles / pN)
lastTile  = floor((ns + 1) * nTiles / pN)
cols      = (lastTile - firstTile) * V
n0        = min(firstTile * V, N - cols)
```

这样每个分片仍只调用一次 Matmul；没有为最后 1～15 列增加第二个 Matmul 对象或额外 kernel。每个返回 C tile 都有完整 V 列，复用原 fast 的行最大值归约。

普通分片相邻连续。最后分片与前一片仅重叠 `delta < V` 个真实列，覆盖的并集恰好为 `[0,N)`。因为 `max(x,x)=x`，重叠不改变最终逐行最大值。先合并 N 分片的逐行 Max，再对真实 M 行做一次 FP32 Sum，避免重复求和，也不引入会破坏全负输出的补零列。

输入寻址和 Host/Device `SetOrgShape` 均保留**真实 N**。虚拟 N 只用于 tile 规划，绝不能作为原始 B 的行跨度。M/K 的真实尾部继续由 SDK 处理；支持 NN、NT、TN、TT 和两种 dtype。

Planner 在 tileM={16,32,64,128}、V={64,128,256} 中选择，同时考虑不均匀分片的最长工作量。V 的下限为 64，避免小尾部把主体拆成大量 16 列的 SDK 迭代。该成本模型没有实测拟合，其选择是否最快仍需平台结果验证。

## 保留与回退

- 删除 R46 新模块、唯一入口 hook 和版本注释后，逐字节恢复原 R43；原 R25/R43 的所有旧函数、常量、分派顺序均未修改。
- Case5 的 R25 小输出策略、Case15 Split-K 以及 R06/R03 等旧路径保留。新分支是原 R43 元数据域的子集，不能把新策略扩散到 Native small-K 等其他域。
- 检查真实 tiling 的 baseM/baseN、singleCore 覆盖范围、usedCoreNum 和迭代顺序。N 分片长度可能不均匀，所以流序检查使用 **ceil(nTiles/pN)**；不能套用原 uniform planner 的 floor。
- 最优估计 plan 不受 SDK 支持时，尝试保守 plan；仍不支持则在 launch 前回到原 R43。只有一个可用核时也回到 R43。
- 每个成功调用只启动一个实际计算 kernel。launch 后发生运行错误会中止，不会用第二次 launch 掩盖错误。

源码隔离不等于已经证明 Judge 的其他 14 点没有波动或退化；完整平台回归仍须检查。

## 本地验证及边界

验证实际抽取的 C++ planner、consumer、Host tiling 调用；使用 CPU Matmul/向量/内存适配器。覆盖 FP16/BF16、四种转置、正反 worker 启动顺序、不同 M/N 尾部、非均匀 M/N 分片和 16～256 列的消费逻辑。

输入包括精确二进制分数随机数据、所有 C 元素为负、唯一最大值在最后一列、最大值在重叠区、全零、K 内抵消。以独立的完整 A×B → Max(N) → Sum(M) 为参考；检查越界、未初始化读取、重复写入和 UB 容量。另有元数据边界、分片覆盖、四种物理布局的地址范围和 tiling 拒绝测试。故意遗漏最后一个尾 tile、把虚拟 N 写成物理 stride 的故障均须被测试检出。

实际数量和源码 SHA256 见 `CPU_CHECKS.json`。这些检查不模拟设备流水、Cube 累加舍入或 KFC 执行，也没有运行真实 CANN tiler。**本地未完成 Bisheng/CANN 编译，未进行 NPU 精度或耗时验证。**

## 这轮如何提交

先只提交 `R46_CASE8_FAST_MAIN_TAIL.asc`，保留全部 15 点的 Pass/耗时结果。以 R43 的约 62.45 μs 为对照；不要再拿 R25 的约 91 μs 当作 R46 的直接基线。

如果结果仍接近 62.5 μs，尚不能仅凭耗时区分“SDK 拒绝后回到 R43”和“新分支实际执行但耗时相当”。先核实实际分派再决定后续修改。若出现明显改善，再交替复测 R43/R46 排除整轮时钟或测评波动。确认其他点没有稳定退化后再晋升。

## 复现与来源

工作区中执行：

```powershell
python V11_impl_r46\build.py
python V11_impl_r46\check.py
python V11_impl_r46\package.py
```

`CONTROL_R43.asc` 是冻结对照，`R43_to_R46.diff` 是全部源码差异。CPU 适配器不进入提交文件。

相关接口依据为官方 [SetTensorB](https://www.hiascend.com/doc_center/source/en/canncommercial/800/apiref/ascendcopapi/atlasascendc_api_07_0632.html) 和 [GetTensorC](https://www.hiascend.com/doc_center/source/en/canncommercial/800/apiref/ascendcopapi/atlasascendc_api_07_0639.html)；实现沿用现有 R43 文件的 Matmul API 调用形式。在线文档和本地参考 SDK 不代替目标 Judge 的编译与执行。

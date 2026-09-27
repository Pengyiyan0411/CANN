# D24 诊断包：冻结 R23，分路径提取 shape

这批文件用于诊断，不能替换 R23 作为长期冲榜版。每份 .asc 都是独立完整提交，只选一份。
当前基线是用户确认的 R23：两轮 15/15 Pass，Case15=15.18/15.18 μs。
CONTROL_R23.asc 与它字节一致；原 R14/R23 均未修改。本包不再包含旧 A–C 阈值扫描。

## 建议顺序

1. **N01–N05**：同时观察 Case5/13/14，分别确认 K32、K64、M≤32、N≤32、B=1。
2. **R7_01–R7_05**：观察 Case7，分别确认 M<128、N<256、macro_occ<cores、K≥512、K≥1024。
3. **L00_K1_CONTROL → L05_SPATIAL_EQ1**：观察 Case15。如果 L00 明显变慢且 L05 复现，
   一次联合探针同时确认 B=1、M≤64、N≤128。

第一批不必一次跑完；前两组可以交叉提交以缩短反馈周期。
每张图保留完整 15 点和文件名，Case6 可以同时免费观察响应。
C00/C01 是新包的 Native/R03 无条件单组压力对照，条件结果不清或需要凭阴性排除时再用。
不需要补旧 A–C 的结果。

## 读数规则

- Native K：N01 是→32；N01 否、N02 是→64；两者否且阳性压力对照有效→128。
- family：N03/N04 是/否→ShortM；否/是→ShortN；其余两组相同响应→Dense。
- Case7 K：R7_04/05 否/否→[256,512)，是/否→[512,1024)，是/是→[1024,8192]；均 32 对齐。
- 阳性要求明显脱离相邻控制波动并接近该路径压力对照；阴性需要有效阳性对照。
  小幅差异记“不确定”，不按全局倍数去噪。相互矛盾的位模式、TLE/编译失败/精度失败均不能当 shape 位。
- **撤回 Case7 K<512 的旧推断**：旧 bypass 信号只有约 2 μs，不足以由不变排除条件。
- **Case15 不再用 R03 bypass**：当前路径已经是更早返回的 Split-K。L 系列只在 Split-K 内退为单分片；
  L00 的耗时必须实测，不能直接套用历史 R14 的 37 μs。

## 按结果追加

L05 若可靠阴性，再做 L01/L02/L03 分别拆开三项条件；L04 判断 MN≤4096；L06 判断原 S≥8。
若已拿到所需信息就停止该组，不追精确 M/N/K。
Case6 先看 N/R7/L00 的响应；仍未知时再做 X6_01/X6_02/X6_03，分别破坏 Macro、Tree、最后 fallback 的并行度。
全无响应也不能把路径全排除，原计划可能接近单组。

## 文件作用域

| 文件（省略 .asc） | 仅作用的路径 | 条件 |
|---|---|---|
| C00_NATIVE_1G | native | `true` |
| C01_R03_1G | residual | `true` |
| N01_K_EQ32 | native | `K==32` |
| N02_K_EQ64 | native | `K==64` |
| N03_M_LE32 | native | `M<=32` |
| N04_N_LE32 | native | `N<=32` |
| N05_B_EQ1 | native | `B==1` |
| R7_01_M_LT128 | residual | `M<128` |
| R7_02_N_LT256 | residual | `N<256` |
| R7_03_MACRO_OCC_LT_CORES | residual | `int64_t(B)*bmms83::UpH(M,128)*bmms83::UpH(N,256)<cores` |
| R7_04_K_GE512 | residual | `K>=512` |
| R7_05_K_GE1024 | residual | `K>=1024` |
| L01_B_EQ1 | split | `B==1` |
| L02_M_LE64 | split | `M<=64` |
| L03_N_LE128 | split | `N<=128` |
| L04_MN_LE4096 | split | `int64_t(M)*N<=4096` |
| L05_SPATIAL_EQ1 | split | `B*p.mTiles*p.nTiles==1` |
| L06_SPLITS_GE8 | split | `p.splits>=8` |
| X6_01_MACRO_1G | macro | `true` |
| X6_02_TREE_1W | tree | `true` |
| X6_03_FALLBACK_1CORE | fallback | `true` |

L00_K1_CONTROL.asc 是上轮 K1 文件的原字节副本。
Native/R03/Macro 的压力计划同步设置 pM=pN=1、tasks=B、blocks=1，再分配 workspace。
这保留全部 batch 的真实计算；没有只改 blocks，也没有把 tasks 错写成 1。

## 已完成检查

设备代码逐字保持 R23；全部干预都在 host。
82236 次实际 host 分派记录检查通过，含 69226 次不命中时完整记录相等；漏更新 tasks 的故障注入被拒绝。
原计划/单组计划各 160 次 Native/R03/Macro/Tree 源码模型执行、80 次重复核对，输出逐位一致。
K1 设备检查继承上轮绑定源码 hash 的结果；Fallback 单核参数本轮检查了 host，不声称覆盖其全部 device 子路。
这些新诊断文件尚未由本地 CANN 编译或 NPU 验证；R23 的平台 Pass 不自动覆盖诊断版。

完整推导、状态表和下一轮优化分支见 DESIGN.md；逐文件 SHA256 在 MANIFEST.json。

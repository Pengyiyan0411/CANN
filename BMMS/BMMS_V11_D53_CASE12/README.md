# D53：基于R52的Case12形状与原始plan诊断

2026-09-28。用户反馈R51没有明显收益、R52有用：本包直接基于R52，保留点1/2及其他已有效策略，**不包含R51**。R43继续冻结。本包是诊断版，命中时主动降低R06并行度，不作为性能基线。

## 本轮先提交这三个

| 顺序 | 完整提交源码 | 检查条件 | Case12 HIT后 | Case12 NO后 |
|---|---|---|---|---|
| 1 | [C12_K_GE1792.asc](C12_K_GE1792.asc) | `K>=1792` | K=1792..2016/32 | K=1536..1760/32 |
| 2 | [C12_M_GE2048.asc](C12_M_GE2048.asc) | `M>=2048` | M=2048..8192/16 | M=1024..2032/16 |
| 3 | [C12_N_GE2048.asc](C12_N_GE2048.asc) | `N>=2048` | N=2048..8192/16 | N=1024..2032/16 |

三份各自是完整独立源码，分别提交，保留完整15点结果与文件名。这三份不局限于Case12，进入R06的其他输入也按同一阈值编码，可顺带读取9–11。

- [CONTROL_R52.asc](CONTROL_R52.asc)与原R52逐字节相同，不必重复跑已有效的基线。
- [C12_00_R06_STRESS_ALL.asc](C12_00_R06_STRESS_ALL.asc)是本包阳性对照。已有同机制校准清楚时可先跳过；本包结果不清楚或出现矛盾时再用。
- 历史正常约120–125微秒，压力对照约1.50–1.51毫秒。读数应明显接近正常或该点的压力对照；不要把某个固定耗时当成所有case通用阈值。
- 小幅波动记为不确定；TLE、编译失败、精度失败都不能解释为shape位。

## 已准备的第二阶段：读取原始plan

下列只在R06内的 `B=1、M/N>=1024、1536<=K<2048` 域生效，按现有证据覆盖Case12而排除Case9/10/11。均先读取未干预的 `observed=MakePlan(...)`，再决定是否压成单组；不会误读压力计划的pM=pN=1。

| 提交文件 | 检查原始字段 |
|---|---|
| [C12_P_PM_GE2.asc](C12_P_PM_GE2.asc) | pM≥2 |
| [C12_P_PM_GE4.asc](C12_P_PM_GE4.asc) | pM≥4 |
| [C12_P_PM_GE8.asc](C12_P_PM_GE8.asc) | pM≥8 |
| [C12_P_PN_GE2.asc](C12_P_PN_GE2.asc) | pN≥2 |
| [C12_P_PN_GE4.asc](C12_P_PN_GE4.asc) | pN≥4 |
| [C12_P_PN_GE8.asc](C12_P_PN_GE8.asc) | pN≥8 |
| [C12_P_BLOCKS_EQ_CORES.asc](C12_P_BLOCKS_EQ_CORES.asc) | blocks等于运行时有效cores |
| [C12_P_TASKS_EQ_CORES.asc](C12_P_TASKS_EQ_CORES.asc) | tasks等于运行时有效cores |

不必全跑：先看shape结果，再选能改变优化决策的项。pM/pN的阈值只能得到区间，例如三个HIT代表≥8，不能写成恰好8。

`tasks=B*pM*pN`、`blocks=min(cores,tasks)`。B=1时若已知pM/pN便可得到tasks；但在实际核数未知、原任务可能超过cores的情况下，blocks==cores和tasks==cores不等价。如果实际为20核组，4×4只有16个task，不能称为20核满占用。

## 实现边界

仅修改 `bmms11r2::TryLaunch` 中生成plan之后、申请workspace之前的几行host代码：

```cpp
const auto observed=MakePlan(B,M,N,K,cores);
auto p=observed;
if (predicate) {
    p.pM=1; p.pN=1; p.tasks=p.B; p.blocks=1;
}
// 随后用p计算RingBytes/PartialBytes/WorkspaceBytes并启动
```

保留全部batch真实计算，tasks不能错误地写成1。未改任何device kernel、共享MakePlan、宏块大小、K分块或dtype/布局分派。

点8的padded路径也调用R06的MakePlan，因此不能把压力逻辑塞进共享planner。本包只干预直接R06启动入口，点8继续原路径。点1/2先返回R52/R50，点7/13/15等其他路线同样不受干预。

## 检查与限制

- 每份探针去掉唯一host干预后，可逐字节恢复R52；未命中的路径没有源码算法改动。
- 89,136次实际host源码分派记录比较通过：21,468次压力计划检查、67,668次未命中记录完全相同。
- 5,808次原始plan条件命中检查；点1/2保护各576次，点8保护1152次，其他已有效路线保护864次。
- 对75组M/N/cores比较K1536与K2016，网格相同；这印证了当前planner没有K评分项。
- R06设备源码与D24/R23用于单组压力检查的设备源码相同，已有历史CPU模型下普通/单组计划各32次macro执行及逐位一致记录。本轮没有重新跑这些device测试；也没有对真实大矩阵进行NPU验证。
- 新探针尚未在CANN编译或NPU测评，host测试中的设备启动采用记录器。

[分派检查](HOST_CHECKS.json)、[继承的设备证据](DEVICE_EVIDENCE.json)、[逐文件hash与修改范围](MANIFEST.json)。

## 为什么暂不重复Case13三个探针

[D24已归档N01–N05](../V11_results/2026-09-27_d24_native/AUDIT.md)中，Case13对B1条件压力约17→98.42微秒，对K32/K64均无响应，对M≤32/N≤32均无响应。结合Native约束，已有 `B=1、K=128、M/N>=48且16对齐` 的证据。再跑K=128与N≥48不能缩小范围。

Case13的R49优化已有效并被R52继承。若后面重开这条线，应围绕实际窄N和现有消费开销提出新的区分条件，而不是重复已确认的下界。

## 下一步判断

形状二分只用于隔离范围，不能凭它断言planner是瓶颈。当前R06的网格评分主要按最忙核tiles/cells/input排序，并要求候选相对基线三个指标各改善至少12.5%；这个保守门槛可能跳过局部折中，但是否影响Case12需要原plan证据。

拿到下一轮结果后，只在Case12可识别域评估候选网格及负载，再做保持device不变的planner消融。若原plan并无明显负载问题，则转而检查K尾块、输入布局和最终归约，不预先改写新kernel，也不把9–12整簇一起换策略。

复现：先运行 `python V11_d53/build.py`，成功后运行 `python V11_d53/check_host.py`。

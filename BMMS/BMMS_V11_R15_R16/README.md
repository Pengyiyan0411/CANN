# R15 / R16提交包

先提交R15_K32_GAPS.asc，再独立提交R16_K16_TAILS.asc；均以R11为父版本。
每次将对应文件完整替换官方code/kernel.asc，保留官方main与CMake，不拼接两个候选。

| 文件 | 用途 |
|---|---|
| R11_CONTROL.asc | 与已交付R11完全相同的对照 |
| R15_K32_GAPS.asc | 新覆盖K=96/160/192/224 |
| R16_K16_TAILS.asc | 新覆盖K=48..8176且K%32==16，与R15独立 |

两版仅调整M/N均16对齐时的K准入，复用已有Cube流水线；保留Tiny/Resident与原生K32/64/128。
不含R13/R14网格变化。R13/R14均Pass，但单次小变化尚不能排除噪声，R11继续作为基线。
若候选出现明显变化，再用R11_CONTROL做相邻复核；保留完整结果与当次T。

本地R15/R16分别628/740次普通源码CPU执行通过，旧域输出与冻结R11一致。
新增域与FP64标杆比较，不等同于目标硬件精度通过。每版3项已知极端数值限制仍存在。
没有本地CANN编译/NPU验证，候选性能与平台正确性均待确认。

SHA256：

- `R11_CONTROL.asc`：`425db189f068ad963dadf2c537a96118b33a5035ef47c5e43dad2f81fd0ad223`
- `R15_K32_GAPS.asc`：`1d1d14c8245ec9af2e9dd6134f299f8692a8b9ba84556d844a68df6252a29f25`
- `R16_K16_TAILS.asc`：`71bc08485e3f3d73c0eeccb9d0a869d79ad1d8264941f7ab933a106022bf15e0`

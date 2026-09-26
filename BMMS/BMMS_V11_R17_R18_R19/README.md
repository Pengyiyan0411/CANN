# R17 / R18 / R19：三个独立R14后代

按用户技术审计计划推进，顺序R17→R18→R19。每份asc完整替换官方code/kernel.asc，
保留官方main/CMake，不能叠加不同文件片段。R14_CONTROL与已通过R14完全相同。

| 文件 | 只改变 |
|---|---|
| R17_R14_K32_GAPS.asc | 将R15的K96/160/192/224覆盖修改迁移到R14 |
| R18_R14_K16_TAILS.asc | 将R16的K%32==16覆盖修改迁移到R14 |
| R19_R14_A_RESIDENT.asc | K256/512且每任务≥2个N宏块，完整A跨N驻留L1 |

R17/R18不是R15/R16原文件；它们保留R14的规划层。R19独立从R14派生，不含覆盖实验。
同父版比较使用R14→候选→R14，保存全部15点及当次T，小变化暂按未分辨处理。

本地普通源码执行和新增地址/搬运/host选择检查通过，具体结果见CPU_CHECKS.json。
合成四N宏块样例中R19的A逻辑读取减少75%，这不是硬件耗时提升比例。
本地没有CANN/NPU验证；每版3项已知极端数值限制仍保留，平台正确性和性能待确认。

SHA256：

- `R14_CONTROL.asc`：`64eb6eeeb10d2418845d2026b9e9fdd2088d0a3ad1decb0a1bfc46d65cfa78fe`
- `R17_R14_K32_GAPS.asc`：`5582d77e80c2b9c80aa3247ce694485e6adfea9639ed79a1d70be229badc97ec`
- `R18_R14_K16_TAILS.asc`：`07cc37d915c68fe00ba7e7396c97b2ef19226dcc981e6331a6d66ec3ade217c5`
- `R19_R14_A_RESIDENT.asc`：`dc54132a5bb6790656b950092d93ee22625887fe119ba02f7cea012384bea06a`

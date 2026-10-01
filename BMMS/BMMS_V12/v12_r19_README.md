> Judge已通过15/15：Case8 46.88 μs、Case15 11.29 μs；r19已冻结为主线。以下本地候选报告保留原始时间点。

# v12_r19 Case8 候选

直接提交 **v12_r19_case8_nz_explicit_tail.asc**。以已接受r12为父版，保留Case15成果。

Case8按stride/转置选择UB内NZ整理，并采用显式归约尾部掩码；其他组合回退原R43。

- 258组、774次精度验证全部通过，含128组Split-K回归。
- 40组合成Case8：两轮耗时中位缩短15.03% / 14.83%；新分支26例中位约26.2%。
- 插桩memcheck的2例无ERROR；race/init仍有父版同类告警，尚未全面闭环，详见报告。

真实Case8形状未知，仍需Judge完整15点验收；r12继续已接受主线。r18保留为研究对照，本轮只提交r19。

[完整报告](../V12_npu_lab/results/case8_20260928/REPORT.md) · [记录](v12_r19_manifest.json)

SHA256：`27ff91a8e886644ba99b68e3a59ed4d5ed0a001039d6c56074df098d4c66c021`

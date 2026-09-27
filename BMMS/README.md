# BatchMatmulMaxSum：R25冻结，Case15单空间任务已确认

2026-09-27：明确标注的L00/L05均15/15 Pass；Case15为36.78/37.11 μs，相对正常约15 μs形成清楚压力响应。
L05阳性确认B=1、M∈{16,32,48,64}、N∈{16,32,...,128}，K4096..8192且32对齐，原空间任务数为1。
L01–L03无需提交。正常Split-K的K分片数仍未知，不能把单空间任务当作单核组。

- [本轮L00/L05结果与解码](V11_results/2026-09-27_d24_l00_l05/AUDIT.md)
- [最新诊断进度](V11_results/2026-09-27_d24_l00_l05/PROGRESS.json)
- [下一份：L04_MN_LE4096](BMMS_V11_D24_Resume/D24/L04_MN_LE4096.asc)
- [随后：L06_SPLITS_GE8](BMMS_V11_D24_Resume/D24/L06_SPLITS_GE8.asc)
- [已完成Case7解码](V11_results/2026-09-27_d24_r7/AUDIT.md)
- [R25保留版](BMMS_V11_R25/R25_NATIVE_TARGETED.asc)
- [D24原字节续跑包](BMMS_V11_D24_续跑包.zip)
- [N01–N05已完成结果](V11_results/2026-09-27_d24_native/AUDIT.md)
- [当前审计](BatchMatmulMaxSum_当前审计报告_2026-09-26.md)

N01–N05、C01/R7组及L00/L05不重跑。接着用原L04/L06确认Case15输出面积和原分片数范围。
Case7保留M<128、N<256、K256..480/32对齐、B<cores结论。Case6仍未定位，必要时用原C00/X6组。
R25成果与原D24诊断基线R23分别保留，所有旧源码/提交包冻结；本轮只归档与核验，没有新内核或本地CANN/NPU测试。

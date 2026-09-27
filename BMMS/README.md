# BatchMatmulMaxSum：R25冻结，D24 Case7已解码

2026-09-27：收到明确标注的C01_R03_1G、R7_01–05六份结果，全部15/15 Pass。
Case7单组压力对照32.79 μs；R7前三项33.58/33.09/34.30 μs，后两项11.44/11.45 μs。
结合源码资格，得到M=16..112、N=16..240（均16对齐），K=256..480（32对齐），B<cores，Dense_MidK。
B和M/N/K精确值、dtype、转置仍未知。K上界来自新强阳性对照，不是旧旁路阴性。

- [本轮完整结果与解码](V11_results/2026-09-27_d24_r7/AUDIT.md)
- [最新诊断进度](V11_results/2026-09-27_d24_r7/PROGRESS.json)
- [下一份：L00_K1_CONTROL](BMMS_V11_D24_Resume/D24/L00_K1_CONTROL.asc)
- [随后：L05_SPATIAL_EQ1](BMMS_V11_D24_Resume/D24/L05_SPATIAL_EQ1.asc)
- [R25保留版](BMMS_V11_R25/R25_NATIVE_TARGETED.asc)
- [D24原字节续跑包](BMMS_V11_D24_续跑包.zip)
- [N01–N05已完成结果](V11_results/2026-09-27_d24_native/AUDIT.md)
- [当前审计](BatchMatmulMaxSum_当前审计报告_2026-09-26.md)

N01–N05及C01/R7组不重跑。L00先标定Case15单K分片信号，再解码L05；后续L/X6按需展开。
Case6尚未定位，当前无强响应不能排除R03。Case15走前置Split-K，本轮R03探针不检测它。
R25成果与原D24诊断基线R23分别保留，所有旧源码/提交包冻结；本轮只归档与核验，没有新内核或本地CANN/NPU测试。

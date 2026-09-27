"""Publish the R25 candidate with an exact frozen snapshot of the D24 audit."""
from pathlib import Path
import json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1];HERE=Path(__file__).resolve().parent;OUT=ROOT/'BMMS_V11_R25'
PREVIOUS='b547e58832417db9aca8e80663a0399e95e21df9'
def write(p,s):p.write_text(s,encoding='utf-8',newline='\n')
def main():
    old=subprocess.check_output(['git','show',PREVIOUS+':BMMS/BatchMatmulMaxSum_当前审计报告_2026-09-26.md'],cwd=ROOT/'CANN_archive')
    snap=ROOT/'audit_current/AUDIT_D24_DELIVERY.md'
    if snap.exists():assert snap.read_bytes()==old
    else:snap.write_bytes(old)
    shutil.copyfile(HERE/'DESIGN.md',OUT/'DESIGN.md');shutil.copyfile(HERE/'BOUNDS_CHECKS.json',OUT/'BOUNDS_CHECKS.json')
    write(OUT/'README.md','''# R25：只验证 Case5 / 13 / 14 的两类特化

**先提交 `R25_NATIVE_TARGETED.asc`。** 每份 .asc 是独立完整文件，不能拼接。
R23 仍为已验证基线；当前没有 R25 平台结果。

| 文件 | 启用内容 | 用途 |
|---|---|---|
| R25_NATIVE_TARGETED.asc | 小矩阵直接输出 + B1 的 N 分片合并 | 本轮首选 |
| R25_SMALL_ONLY.asc | 仅小矩阵路径 | 若需隔离 Case5 收益/问题 |
| R25_DENSE_ONLY.asc | 仅 B1 路径 | 若需隔离 Case13/14 收益/问题 |
| CONTROL_R23.asc | 冻结 R23，字节一致 | 相邻性能对照 |

本批探针已支持 Case5=K128、M/N16或32、B>1；Case13/14=K128、M/N>32、B1。
新分派只在原 Native 内使用这两个互斥条件，还要求原 blocks>1。未命中时继续原内核，
不改 Cube 点积、host 分核、Macro/R03/Split-K、K32/64 或其他 family。

- Case5：整 batch 由一个 AIV 直接 Max→Sum→输出，去掉 partial 往返和全局屏障。
- Case13/14：N 分片用单次二维 DMA 收集到 UB 做树形 Max，保留原 M 求和和一次全局同步。

验证顺序：先 R25 完整 15/15；与相邻 CONTROL_R23 比较全部 15 点。
明显收益再确认一次；落在本轮控制波动内的微小变化记未分辨。不用不同批次最低值拼接成绩。
若 5/13/14 中一类改善、另一类退化，可用对应 ONLY 文件保留已有效的一类；不必预先全跑。
其他点若有超出相邻控制波动的稳定退化，暂不合并，保留 R23。
这轮验收完成之前不继续推进其他测试点，也不要求补新探针。

本地完成源码 CPU 模型与 host 分派/边界检查；**未做 CANN 编译、未做 NPU 测试**。
CPU 输出一致和非目标分派相同不能替代平台的正确性及性能验收。详情见 DESIGN.md / *_CHECKS.json。
''')
    write(ROOT/'BatchMatmulMaxSum_当前审计报告_2026-09-26.md','''# 当前审计：N01–N05 已定位三点，交付 R25 特化候选

2026-09-27。用户明确要求直接优化 5/13/14，先验收完整结果，再推进其他点。
R23 是当前已验证基线；R25 尚待平台编译、正确性和性能结果。原 R14/R23/D24 文件全部冻结。

| 测试点 | 本轮探针结论 | R25 改动 |
|---|---|---|
| 5 | K128，M/N∈{16,32}，B>1，Native Dense_SmallK | 一个 AIV 完成整 batch 的 Max/Sum，去掉跨核组汇合 |
| 13 / 14 | K128，M/N≥48 且16对齐，B1，Native Dense_SmallK | 成批收集 N 分片，UB 树形 Max，保留原 M 求和 |

N03/N04 对 Case5 是本批有效阳性校准；N05 对 Case13/14 是有效阳性校准。
因此 N01/N02 双阴性可在固定 K 集合中排除 32/64，当前无需再补 C00。
五份提交均 15/15 Pass：[完整结果和原图](V11_results/2026-09-27_d24_native/AUDIT.md)。
Case6 仍未定位；Case7/15 已有证据保留，本轮不再推进它们。

R25 仅在原 Native 路径中按上述两类元数据分派，并要求原计划 blocks>1。
分核、Cube 生产者、packet 布局、workspace 契约不变；未命中输入发射原内核。
原版和候选各 222 次源码模型及70次隔离尾段检查，普通输出逐位一致；
18,828 次实际 host 分派检查中，18,444 次未命中记录完全等于 R23。
容量和覆盖边界另作穷举；三种故障注入均被拒绝。
[实现、API 依据与限制](V11_native_targeted25/DESIGN.md)。

这些检查没有包含本地 CANN/NPU；未知测试点元数据不完整，不能预先保证其真实时延不退化。
平台需先验证完整 15/15，并对照相邻 R23 的逐点波动。R25 有效前不替换 SOTA，也不开始其他点。

先提交 [R25_NATIVE_TARGETED.asc](BMMS_V11_R25/R25_NATIVE_TARGETED.asc)。
[完整提交包](BMMS_V11_R25_提交包.zip) 含两份独立 ONLY 消融和 R23 原字节控制。
上轮审计保存为 [D24 交付时快照](audit_current/AUDIT_D24_DELIVERY.md)。
''')
    readme='''# BatchMatmulMaxSum：R23 基线，R25 Native 三点特化候选

N01–N05 五份均15/15，通过同批阳性校准定位 Case5/13/14 均为 K128。
Case5 是多 batch 小输出，13/14 是单 batch 且 M/N>32。R25 仅优化这两类原 Native 输入。
先验收完整15点与非目标退化，再推进其他点。R23 仍是已验证基线；不再要求额外 shape probes。

- [首选完整提交文件](BMMS_V11_R25/R25_NATIVE_TARGETED.asc)
- [R25 提交包](BMMS_V11_R25_提交包.zip)
- [提交与回退说明](BMMS_V11_R25/README.md)
- [设计和验证边界](V11_native_targeted25/DESIGN.md)
- [N01–N05 原始结果](V11_results/2026-09-27_d24_native/AUDIT.md)
- [当前审计](BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [冻结 R23](BMMS_V11_R23/R23_SPLIT_K.asc)

```powershell
python V11_native_targeted25/build.py
python V11_native_targeted25/run_checks.py
python V11_native_targeted25/check_host.py
python V11_native_targeted25/check_bounds.py
python V11_native_targeted25/record_results.py
python V11_native_targeted25/update_docs.py
python V11_native_targeted25/package.py
```

本地 CPU/host 检查通过，未做 CANN/NPU 验证。R25 平台结果待回传；历史源码、提交包、审计快照保留。
'''
    write(ROOT/'README.md',readme)
    import re
    write(HERE/'CANN_README.md',re.sub(r'\]\((?!https?://)([^)]+)\)',r'](BMMS/\1)',readme).replace('```powershell\n','```powershell\ncd BMMS\n'))
    print('Updated current audit and R25 delivery docs; historical sources preserved.')
if __name__=='__main__':main()

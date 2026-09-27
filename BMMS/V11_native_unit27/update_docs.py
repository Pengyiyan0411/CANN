"""Record the R26 rejection and R27 candidate without changing frozen artifacts."""
from pathlib import Path
import shutil,subprocess
ROOT=Path(__file__).resolve().parents[1];HERE=Path(__file__).resolve().parent;OUT=ROOT/'BMMS_V11_R27'
PREVIOUS='596a019de35ad845f0a2341e847286358c0d2da8'
def write(p,s):p.write_text(s,encoding='utf-8',newline='\n')
def main():
    snap=ROOT/'audit_current/AUDIT_R26_DELIVERY.md'
    previous=subprocess.check_output(['git','show',PREVIOUS+':BMMS/BatchMatmulMaxSum_当前审计报告_2026-09-26.md'],cwd=ROOT/'CANN_archive')
    if snap.exists():assert snap.read_bytes()==previous
    else:snap.write_bytes(previous)
    readme='''# BatchMatmulMaxSum：R26不升级，R25保留，R27单独验证Cube同步

最新截图按交付上下文归为R26：15/15 Pass，Case13/14为17.26/13.77 μs，没有收益证据。
Case5为6.86 μs，高于R25的6.60/6.45 μs；没有把这个变化直接解释成噪声。
R25继续作为工作基线。R27只替换原Native、B1/K128/M,N>32/blocks>1的MMAD→FIX同步方式。
Case5和R25所有消费者保留；R26 packet消费者不携带。尚无R27设备性能结果。

- [R27完整提交源码](BMMS_V11_R27/R27_DENSE_UNITFLAG.asc)
- [R27提交包，含原字节R25对照](BMMS_V11_R27_提交包.zip)
- [验证顺序和边界](BMMS_V11_R27/README.md)
- [重新审阅、同步说明及API依据](V11_native_unit27/DESIGN.md)
- [最新截图与否定结果归档](V11_results/2026-09-27_r26_observed/AUDIT.md)
- [当前审计报告](BatchMatmulMaxSum_当前审计报告_2026-09-26.md)

源码模型与host分派检查通过；没有本地CANN编译、NPU运行或性能提升证明。
本轮只提交一个候选，必须先检查全部15点，再验13/14可重复下降和5保持。
若无收益即回退R25；旧源码、截图、ZIP保持冻结。

```powershell
python V11_native_unit27/build.py
python V11_native_unit27/check_host.py
python V11_native_unit27/run_checks.py
python V11_native_unit27/record_results.py
python V11_native_unit27/update_docs.py
python V11_native_unit27/package.py
```
'''
    write(ROOT/'README.md',readme)
    github=readme
    for prefix in ['BMMS_V11_R27/','BMMS_V11_R27_提交包.zip','V11_native_unit27/DESIGN.md','V11_results/','BatchMatmulMaxSum_当前审计报告_2026-09-26.md']:
        github=github.replace(']('+prefix,'](BMMS/'+prefix)
    github=github.replace('```powershell\n','```powershell\ncd BMMS\n')
    write(HERE/'CANN_README.md',github)
    write(ROOT/'BatchMatmulMaxSum_当前审计报告_2026-09-26.md','''# 当前审计：R26无收益证据，R27验证Native dense的Cube同步

2026-09-27。当前仍只优化13/14并保留5；没有NPU测试环境。
最新图按交付上下文归为R26_DENSE_PACKET，文件名与平台源码hash没有再次独立确认。
15/15 Pass，误差栏0.00%，完整15点数据、原图、hash见[结果归档](V11_results/2026-09-27_r26_observed/AUDIT.md)。

| Case | R25 两次 μs | R26本次 μs | 决定 |
|---|---:|---:|---|
| 5 | 6.60 / 6.45 | 6.86 | 保留R25，不声称已排除小幅退化 |
| 13 | 16.80 / 16.91 | 17.26 | 无收益证据 |
| 14 | 13.84 / 13.63 | 13.77 | 与此前观测重叠，无收益证据 |
| 15 | 15.30 / 15.03 | 15.43 | 保留既有Split-K路径 |

撤回R26升级推荐，工作基线仍为冻结R25。旧两次值不是置信区间，不用跨点缩放或拼接最低值“去噪”。

重新核查得到三个结论：

1. 基于已标定N01–N05信号和正确的文件对应关系，13/14应命中R26；实际host源码未发现绕过目标分支的问题。
2. R26减少消费端DMA调用，未减少C有效字节量、Cube计算或跨核同步次数。净收益为零不等于已经定位唯一硬件瓶颈。
3. M_FIX只约束FIX等待本块MMAD；旧双缓冲有跨块重叠。不能将其误读成整个Scalar/流水串行。

R27从R25重新派生，仅在原Native后限制B1/K128/M,N>32/blocks>1。
完整K的MMAD和对应完整Fixpipe成对启用UnitFlag=3，删除本块M_FIX事件。
保留L0A/B和L0C复用保护、原packet READY/FREE，给小尾块补PIPE_M依赖。
设置与NZ→ND相配的计算方向，并在排空后恢复默认方向。
所有R25消费者、Case5原内核、plan、workspace、其他路由均保持；不携带R26包消费改动。
依赖审阅、资源说明和官方支持依据见[设计文档](V11_native_unit27/DESIGN.md)。

最终R25/R27源码模型各318次运行、70次隔离合并和194次重复检查，普通输出逐位一致；
6276次host对照中6164次域外调用记录相同，含80次Case5元数据组合。
UnitFlag单边启用、部分搬出、漏小块依赖及扩大路由等故障注入均被拒绝。
所有数据工作量与显式资源不变。示例32块的M_FIX等待从32降为0，这不代表32倍或任何确定时间收益。

没有本地CANN编译或NPU测试，CPU模型也不证明真实硬件时序、全部极端数值及性能。
R27只是一个依据明确的待验证候选，不能称为新的SOTA。

先提交[R27_DENSE_UNITFLAG.asc](BMMS_V11_R27/R27_DENSE_UNITFLAG.asc)。
[提交包](BMMS_V11_R27_提交包.zip)含原字节CONTROL_R25，验证全部15点和5保持后，才判断13/14收益。
若无可重复下降，回退R25，不扩大这项改动，不推进其他点。
上轮报告保存在[原样快照](audit_current/AUDIT_R26_DELIVERY.md)。
''')
    write(OUT/'README.md','''# R27_DENSE_UNITFLAG 提交说明

先提交 `R27_DENSE_UNITFLAG.asc`：完整单文件，无需拼接。
`CONTROL_R25.asc` 与冻结的 `R25_NATIVE_TARGETED.asc` 逐字相同，可作回退或相邻对照。
不要再把R26作为默认升级；最新图13/14没有收益证据。

R27保留R25的Case5路径、消费者、分核和分配；仅在Native单batch K128且M/N>32、blocks>1时更换Cube同步。
UnitFlag替换MMAD→FIX整块等待，尾块依赖和所有槽位复用保护保留。
没有合入R26的packet读取，没有更改其他测试点策略。

本地通过实际C++源码CPU模型和host对照；尚未CANN编译或NPU运行，不保证平台提速。

验收顺序：

1. 全部15点Pass；若编译失败、错误或运行超时，立即回退CONTROL_R25。
2. 查看13/14是否明显且可重复下降，同时核对5、15和其余点。
3. 仍只有小幅变化时，必要时用包内R25做相邻对照；无稳定收益则保留R25。

只需先验证这个候选，不继续旧探针，不申请额外算力。
源码SHA256在MANIFEST.json。CPU_CHECKS/HOST_CHECKS保存绑定源码的结果与验证边界。
详细审阅和API依据在DESIGN.md。CPU逐位一致不等同于设备编译后的逐位一致。

在完整归档仓库内复现：

```powershell
python V11_native_unit27/build.py
python V11_native_unit27/check_host.py
python V11_native_unit27/run_checks.py
python V11_native_unit27/update_docs.py
python V11_native_unit27/package.py
```
''')
    shutil.copyfile(HERE/'DESIGN.md',OUT/'DESIGN.md')
    print('R26 audit frozen; current R25 baseline and R27 pending status written.')
if __name__=='__main__':main()

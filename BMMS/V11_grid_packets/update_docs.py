"""Publish the latest evidence while preserving delivery-time history."""
from pathlib import Path
import hashlib
import json
import shutil
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;OUT=ROOT/'BMMS_V11_R07_R08'
def write(p,s):p.write_text(s,encoding='utf-8',newline='\n')
def main():
    result=json.loads((ROOT/'V11_results/2026-09-26_r05_r06_submission/RESULT.json').read_text(encoding='utf-8'))
    checks=json.loads((HERE/'CHECKS.json').read_text(encoding='utf-8'))
    manifest=json.loads((OUT/'MANIFEST.json').read_text(encoding='utf-8'))
    assert checks['ordinary_outputs_equal_bitwise'] and all(n['rejected'] for n in checks['negative_controls'].values())
    for row in [manifest['control'],*manifest['variants']]:
        assert hashlib.sha256((OUT/row['file']).read_bytes()).hexdigest()==row['sha256']==checks['sources'][row['file']]
    audit=ROOT/'BatchMatmulMaxSum_当前审计报告_2026-09-26.md'
    snapshot=ROOT/'audit_current/AUDIT_R05_R06_DELIVERY.md'
    if not snapshot.exists():
        assert 'R04反馈与R05/R06底层优化' in audit.read_text(encoding='utf-8')
        shutil.copyfile(audit,snapshot)
    table='\n'.join(f'| {k} | {v:.6f} |' for k,v in result['scores_same_current_T'].items())
    point_table='\n'.join(f'| {r["case"]} | {r["R04_us"]:.2f} | {r["R05_us"]:.2f} | {r["R06_us"]:.2f} | {r["T_us"]:.2f} |' for r in result['rows'])
    write(audit,f'''# BatchMatmulMaxSum 当前审计：R05/R06反馈与R07/R08

2026-09-26。用户明确标注R05、R06均15/15 Pass，并提醒测评有波动。当前只有每版一次
观测，不能完全分离测量噪声和代码效应。本轮保存原始反馈，保持R04为对照基线，
实现两个独立候选R07、R08及同源R04控制文件。本地未使用CANN/NPU环境。

## 本轮判断

R05/R06没有显示可靠的大点提速，暂不合并两项改动。R05单次总分最高，先保留为观测结果，
不宣称已确认更快；R06也不能仅凭这次小幅回退认定稳定退化。
此前对R04点15从R03 37.08降到35.76μs的小幅变化，同样不作为稳定收益。

| 版本 | 按本轮T复算分数 |
|---|---:|
{table}
| R07 / R08 | 待平台反馈 |

点5的T从2.36变为1.95μs，R04因此由上一口径34.496451变为34.299997。
必须统一T后比较分数；评估代码变化时优先比较原始耗时，不把基准更新当作代码退化。
当前三版分数差没有重复测量支持，不给出统计显著性。

| 点 | R04 μs | R05 μs | R06 μs | 本轮T μs |
|---|---:|---:|---:|---:|
{point_table}

R05点9–12为−0.17%、−2.00%、+0.11%、+0.57%；R06为+1.89%、−0.01%、+0.81%、+1.00%。
这些变化未足以确认稳定收益。点8、13的差距仍大，但hidden shape/profiler均缺失，
不能据点号锁定kernel，也不能用某个小点的比例统一校正所有点。
[原图、逐点数据和波动审计](V11_results/2026-09-26_r05_r06_submission/AUDIT.md)。

## R07：核间工作量均衡

只修改宏块路径的host调度，保持全部device计算源码、公开guard和核数上限。
按实际task步进计算每个核组的宏块个数、活跃M×N单元数和输入读取量，搜索pM/pN网格。
三种峰值都比原网格至少降低12.5%时才允许改变，否则返回R04网格。
该门槛是结构上的选择条件，不是性能承诺或测量噪声边界。

独立逐宏块检查3190组合法形状/核数，其中866组调整，确认覆盖唯一、无遗漏、无空分片。
全局点积及输入/C搬运不增加。例如合成B8/M4096/N4096/K256、20核组，最忙核宏块数
352→224；B1/M4096/N4096/K256、20核组为32→26。不是隐藏点shape或设备耗时。

pN增加会增加partial和最后Max循环，跨任务局部性及host规划成本也可能抵消收益；
因此工作量更均衡仍需平台验证。工作区继续由所选Plan计算，不沿用旧pN的partial容量。

## R08：小K输出按四块成包

原生K32/64/128路径沿用R04的输入驻留和计算，改为两个GM包槽，每包四个微块。
整包Fixpipe结束才发READY，两个AIV各读完后才FREE；尾包显式发布和回收。
包序号跨task/batch连续，本地L0C两槽仍独立同步。大K残余共享消费者保持原样。

控制例B1/M256/N2048/K32、1核组中，READY 64→16、FREE 128→32；计算、输入搬运、
C读写及Vector归约计数均不变。GM ring从64KiB增为256KiB/核组，片上资源不变。
代价是首次消费等整包、更大的GM工作集；短流可能没有收益。

两版均从R04独立派生，R07不含R08，亦不包含R05/R06。设计、地址公式、官方同步接口
依据和差异文件见 [V11_grid_packets](V11_grid_packets/DESIGN.md)。

## 检查结论

| 检查 | 结果 |
|---|---|
| 普通源码CPU运行 | R04/R07/R08各356次，精度失败0，普通输出逐位一致 |
| 重复输出 | 每版178对逐位核对 |
| 既有调度 / guard | 每版4494 / 7560项 |
| 独立网格覆盖 | 3190组；866组按门槛调整 |
| 覆盖范围 | 四布局、双dtype、小K/大K、尾M/N/K、负数/零、跨组/跨任务、尾包1/2/3块、连续包复用 |
| 提前FREE故障注入 | 所有权检查拒绝 |
| 漏尾包READY故障注入 | 同步超时捕获 |
| 既有极端数值 | 每版3项消去/BF16中间溢出限制仍复现，未宣称修复 |
| CANN编译 / NPU | 本地均未执行，候选平台结果待反馈 |

检查执行实际抽取的源码，但不是硬件仿真；不能认证真实流水可见性、舍入或时延。
[CHECKS.json](V11_grid_packets/CHECKS.json)绑定源码及检查器SHA，
[GRID_CHECKS.json](V11_grid_packets/GRID_CHECKS.json)保留调度例子。

## 交付与抗波动比较

建议提交顺序：**R04 → R07 → R04 → R08 → R04**。提交包附原样R04_CONTROL.asc，
与此前冻结R04逐字节一致；R07、R08均单独整体替换官方`code/kernel.asc`。
保存每次全部15点和T，比较候选与前后相邻控制的原始耗时，再统一最新T复算总分。
改善仍落在两次控制的变化区间内，先记为“收益未分辨”；贴近边界再复测候选。
区间外的一次观测也不是统计显著性证明，不拼接各次最短成绩。

[提交包](BMMS_V11_R07_R08_提交包.zip) / [使用说明](BMMS_V11_R07_R08/README.md)。
之前交付时的状态保存于 [R05/R06交付快照](audit_current/AUDIT_R05_R06_DELIVERY.md)。
原源码和ZIP未修改。代码及结果归档至 [CANN/v11](https://github.com/Pengyiyan0411/CANN/tree/v11/BMMS)，
本地ARCHIVE_STATUS.json记录推送和文件核验结果。本轮继续平台反馈，不申请测试环境。
''')
    hashes='\n'.join(f'- `{r["file"]}`：`{r["sha256"]}`' for r in [manifest['control'],*manifest['variants']])
    write(OUT/'README.md',f'''# R07 / R08 提交说明（附原样R04控制）

建议顺序：**R04_CONTROL → R07 → R04_CONTROL → R08 → R04_CONTROL**。
每次选择一份`.asc`整体替换官方`code/kernel.asc`，保留官方run_kernel入口、main和CMake。
不额外设置ASCENDC_CUBE_ONLY，不手动合并源码。

- R04_CONTROL.asc：原冻结R04的逐字节副本，用来观察本轮测评波动。
- R07_BALANCED_GRID.asc：只改宏块host调度，降低最忙核工作量；公开路由和device计算不变。
- R08_NATIVE_PACKETS.asc：只改原生K32/64/128输出协议，每四个微块成包；大K残余消费者不变。

R07/R08分别从R04派生，互不包含，亦不含R05/R06。两版均待平台编译、精度及性能反馈。
本轮R05/R06均15/15 Pass，同最新T复算R04 34.299997、R05 34.603422、R06 34.127486。
用户提醒有波动，单次分数差不算稳定收益；点5的T已从2.36降到1.95μs。

每次保留版本标签、全部15点及T；若编译/精度失败，保留完整日志。
用候选前后相邻两次R04的原始耗时比较；收益落在控制变化区间内先记为未分辨。
不做统一比例噪声校正、不取各次逐点最小值；接近边界再复测候选。
若提交次数需要精简，可以先做R04→R07→R04，然后再测试R08。

本地三版各356次普通源码CPU运行通过，178对重复输出核对，普通输出逐位一致。
3190组独立网格审计通过；故意提前FREE和遗漏尾包READY均被捕获。
原有3项极端数值限制保留。未在本地CANN编译/NPU运行，CPU检查不是硬件仿真。

R07的最忙核工作量下降不代表同倍数提速；增加pN也增加partial归约开销。
R08控制例握手降到1/4，GM ring由64KiB增为256KiB/核组，片上资源保持R04。
短输出流的首次等待可能抵消握手收益。

SHA256：

{hashes}

MANIFEST与CPU_CHECKS记录同一源码SHA；详细设计和检查器见仓库V11_grid_packets目录。
''')
    write(ROOT/'README.md','''# BatchMatmulMaxSum：R05/R06通过，推进R07/R08

R05/R06均由用户明确标注15/15 Pass，但测评有波动，未证明稳定提速。
同最新T复算：R04 34.299997、R05 34.603422、R06 34.127486；点5的T已降到1.95μs。
保留R04作对照，两个新候选分别测试核间均衡和小K输出成包，不合并R05/R06。

- [提交包：R04控制、R07、R08](BMMS_V11_R07_R08_提交包.zip) / [使用说明](BMMS_V11_R07_R08/README.md)
- [当前审计](BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [R05/R06原图和波动分析](V11_results/2026-09-26_r05_r06_submission/AUDIT.md)
- [本轮设计](V11_grid_packets/DESIGN.md) / [检查证据](V11_grid_packets/CHECKS.json)
- [原R04](BMMS_V11_R04/R04_MACRO_RING_RESIDUAL.asc) / [历史交付状态](audit_current/AUDIT_R05_R06_DELIVERY.md)

建议R04→R07→R04→R08→R04，每次整体替换官方code/kernel.asc，保存全部15点和T。
候选变化落在相邻控制的波动区间内时记为未分辨，不拼接各次最短成绩。

三版各356次普通源码CPU运行通过，两个故障注入被拒绝；3190组网格审计通过。
既有3项极端数值限制保留，本地未CANN编译/NPU测试，R07/R08仍待平台反馈。

```bash
python V11_grid_packets/build.py
python V11_grid_packets/run_checks.py
python V11_grid_packets/update_docs.py
python V11_grid_packets/package.py
```

归档：[CANN/v11](https://github.com/Pengyiyan0411/CANN/tree/v11/BMMS)。
历史文档保留交付当时状态，最新结论以当前审计和结果记录为准。
''')
    write(HERE/'CANN_README.md','''# CANN

BatchMatmulMaxSum算子归档，当前代码和证据位于v11分支。
用户确认R05/R06均15/15 Pass，并提醒测评波动。按最新T复算R04 34.299997、
R05 34.603422、R06 34.127486；单次差异不认定稳定收益，保留R04作控制。

下一轮独立候选：R07_BALANCED_GRID只改宏块host调度；R08_NATIVE_PACKETS只改小K输出协议。
提交包附原样R04，建议R04→R07→R04→R08→R04，用相邻控制观察波动。

- [提交包](BMMS/BMMS_V11_R07_R08_提交包.zip) / [使用说明](BMMS/BMMS_V11_R07_R08/README.md)
- [当前审计](BMMS/BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [R05/R06截图与结果](BMMS/V11_results/2026-09-26_r05_r06_submission/AUDIT.md)
- [设计](BMMS/V11_grid_packets/DESIGN.md) / [源码CPU检查](BMMS/V11_grid_packets/CHECKS.json)
- [归档SHA清单](BMMS/ARCHIVE_MANIFEST.json) / [复现说明](BMMS/README.md)

R04/R07/R08各356次普通源码CPU运行通过，3190组独立网格审计及两个故障注入检查通过。
原有3项极端数值限制保留；R07/R08本地未CANN编译或NPU测试，平台结果待反馈。
源码工作量或握手次数下降不作为设备时延预测。历史源码、ZIP和交付时状态原样保留。
''')
    print('Current audit and submission docs updated; previous delivery snapshot preserved.')
if __name__=='__main__':main()

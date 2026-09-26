"""Write the current audit and delivery notes without rewriting older evidence."""
from pathlib import Path
import hashlib
import json
import shutil
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;OUT=ROOT/'BMMS_V11_R09_R10'
def write(p,s):p.write_text(s,encoding='utf-8',newline='\n')
def main():
    result=json.loads((ROOT/'V11_results/2026-09-26_r07_r08_submission/RESULT.json').read_text(encoding='utf-8'))
    checks=json.loads((HERE/'CHECKS.json').read_text(encoding='utf-8'))
    manifest=json.loads((OUT/'MANIFEST.json').read_text(encoding='utf-8'))
    diagnosis=json.loads((HERE/'R07_HOST_DIAGNOSIS.json').read_text(encoding='utf-8'))
    assert checks['ordinary_outputs_equal_bitwise'] and all(v['rejected'] for v in checks['negative_controls'].values())
    assert result['evidence']['R07']['failed_case']==5 and result['evidence']['R07']['failure_stage']=='runtime'
    for row in [manifest['control'],*manifest['variants']]:
        assert hashlib.sha256((OUT/row['file']).read_bytes()).hexdigest()==row['sha256']==checks['sources'][row['file']]
    audit=ROOT/'BatchMatmulMaxSum_当前审计报告_2026-09-26.md'
    snapshot=ROOT/'audit_current/AUDIT_R07_R08_DELIVERY.md'
    if not snapshot.exists():
        assert 'R05/R06反馈与R07/R08' in audit.read_text(encoding='utf-8')
        shutil.copyfile(audit,snapshot)
    scores='\n'.join(f'| {k} | {v:.6f} | 15/15 Pass，单次观测 |' for k,v in result['scores_same_current_T'].items())
    points='\n'.join(f'| {r["case"]} | {r["R04_us"]:.2f} | {r["R05_us"]:.2f} | {r["R06_us"]:.2f} | {r["R08_us"]:.2f} | {r["T_us"]:.2f} | {r["R08_vs_R04_time_delta_pct"]:+.2f}% |' for r in result['rows'])
    bench='\n'.join(f'| {"×".join(map(str,r["shape"]))} | {r["cores"]} | {r["R07_median_host_us"]:.3f} | {r["R10_median_host_us"]:.3f} |' for r in diagnosis['runs']['-O2'] if r['shape'][1]>=4096 and r['shape'][0]==1)
    write(audit,f'''# BatchMatmulMaxSum 当前审计：R08通过，R07点5运行超时，推进R09/R10

2026-09-26。用户明确确认R08截图15/15 Pass；R07在点5运行阶段TLE。
R08暂作开发父版，R04继续冻结；R07未通过，不合并其调度搜索。新候选R09/R10均从R08
独立派生，保留原样R08控制文件。本地无CANN/NPU环境，继续平台提交。

## 证据与当前判断

| 版本 | 按最新T复算分数 | 状态 |
|---|---:|---|
{scores}
| R07 | 无有效总分 | 用户确认点5运行阶段TLE，未提供运行日志 |
| R09 / R10 | 待测 | 已完成源码CPU检查和交付 |

点5的T从1.95降至1.90μs；所有历史分数按同一最新T复算，旧图/旧结果本身保留。
R04的版本归属仍按前轮上下文记录，其余上述反馈有用户明确标签；没有平台源码hash。

| 点 | R04 μs | R05 μs | R06 μs | R08 μs | 最新T μs | R08对R04耗时变化 |
|---|---:|---:|---:|---:|---:|---:|
{points}

点13为18.90→16.57μs（−12.33%），点14为15.28→14.34μs（−6.15%），是R08主要的
正向观测。R08总分较同T下R04约+0.532分，但目前每版仅一次测量，没有相邻同版控制，
不能称已排除波动或统计显著。其他多点变化仍接近此前提交间差异。
hidden shape未公开，不能断言点13/14必然对应原生小K分支。
[原始截图与数据](V11_results/2026-09-26_r07_r08_submission/AUDIT.md)。

## R07运行超时审查

确认的是点5运行阶段TLE；未知的是输入shape、超时阈值及设备错误日志。
R07只改宏块host规划，device源码、flag和循环次序保持R04。原独立任务遍历检查通过，
这不足以证明硬件不会卡死。入口保留batch调度及MIX(1,2)，启动核数不增加。
自定义READY/FREE占4–7，官方SyncAll硬同步占11–14，没有直接flag ID重叠。
接口依据见[本轮设计及官方引用](V11_recovery/DESIGN.md)。

另已确认R07规划本身有明显CPU成本。本地g++ -O2对**实际规划源码**微基准：

| 合成B×M×N×K | 合成核组数 | R07 host μs/次 | R10 host μs/次 |
|---|---:|---:|---:|
{bench}

各数值是5组、每组100次调用的组均值中位数；并非平台NPU时延。R07最多在该组样例中
遍历509候选、78244次任务；R10只查因数对并用闭式工作量。host成本已被显著压缩，
但**点5TLE根因仍未确认，R10也不是已验证的修复**。
[微基准和来源SHA](V11_recovery/R07_HOST_DIAGNOSIS.json)。

## 下一版实现

| 候选 | 相对R08的唯一方向 | 代价/待验证项 |
|---|---|---|
| R09_RESIDUAL_PACKETS | 残余大K按四个微块一次READY，复用R08成包消费者 | GM ring 64→256KiB/组，首次消费可能更晚 |
| R10_SINGLE_WAVE_GRID | 只对原本每核一个任务的宏块布局调整因数网格，闭式整数评分 | pN增加可能增加partial归约；仍需检查是否超时 |

R09保持单L0C的FIX_M保护、完整K累加和原输入双缓冲；显式处理不足四块的尾包。
B1/M64/N2048/K256、1核组控制例中，READY 16→4、FREE 32→8，输入/L0/C搬运、
MMAD、Fixpipe和Vector归约计数全部不变。没有将握手计数下降等同于4倍提速。

R10只在原tasks==cores时调整，候选仍tasks==cores，所有原多任务/欠占用Plan保持原值。
三个最忙核工作量指标都至少下降12.5%才接受；这是结构门槛，不是噪声阈值。
合成B1/M4096/N4096/K256、20核组：20×1→5×4，最忙核32→28个宏块，任务数仍20。
R07同例曾选5×16、80任务。两版都保留R08原生小K路径，不含R05/R06，不互相包含。
[实现设计](V11_recovery/DESIGN.md)与同目录diff保留全部改动。

## 验证边界

| 检查 | 结果 |
|---|---|
| 普通源码CPU运行 | R08/R09/R10各444次，精度失败0；三版普通输出逐位一致 |
| 重复运行 | 每版222对输出逐位核对 |
| 原调度 / guard | 每版4494 / 7560项 |
| 独立网格审计 | 6758组，107组调整；核数/任务数、唯一覆盖、全局工作量检查通过 |
| 尾块公式 | 25088项实际分片枚举核对通过 |
| 残余提前FREE / 漏尾包READY | 分别触发所有权错误 / 模型等待超时 |
| 片上资源 | 三版峰值相同，未增加UB/L1/L0需求 |
| 既有极端数值 | 每版3项消去/BF16中间溢出限制仍复现，未修复 |
| CANN编译 / NPU | 本地未执行；R09/R10平台结果待反馈 |

测试覆盖四布局、双dtype、负值/零、M/N/K尾块、包槽回绕、跨任务/batch、长K/长M，
也实际运行了会改变R10网格的形状。CPU模型不能证明硬件流水、缓存、舍入与时延。
[CHECKS.json](V11_recovery/CHECKS.json)绑定检查器和提交源码SHA。

## 提交与归档

优先 **R08_CONTROL → R09 → R08_CONTROL**；随后 **R10 → R08_CONTROL**。
每份asc单独整体替换官方code/kernel.asc，沿用官方main/CMake，不手动叠加。
用候选前后控制的逐点耗时比较，保存每次15点与当次T；区间内变化先记为未分辨，
边界附近再复测。单次区间外结果仍不称统计显著，不做全局缩放，不拼接不同提交的最短点。

[提交包](BMMS_V11_R09_R10_提交包.zip) / [使用说明](BMMS_V11_R09_R10/README.md)。
原R07/R08源码及ZIP完整保留，[上轮交付审计快照](audit_current/AUDIT_R07_R08_DELIVERY.md)
保留当时“待反馈”状态，本报告与结果目录更新为当前结论。
归档目标[CANN/v11](https://github.com/Pengyiyan0411/CANN/tree/v11/BMMS)，实际推送状态见
本地ARCHIVE_STATUS.json。本轮不要求新增测试环境。
''')
    hashes='\n'.join(f'- `{r["file"]}`：`{r["sha256"]}`' for r in [manifest['control'],*manifest['variants']])
    write(OUT/'README.md',f'''# R09 / R10提交包：附原样R08控制

先提交 **R08_CONTROL → R09 → R08_CONTROL**，再 **R10 → R08_CONTROL**。
每次仅选一份asc整体替换官方`code/kernel.asc`，保留官方main/CMake，不改入口ABI，
不另加ASCENDC_CUBE_ONLY，不手动合并候选。R09优先，R10为受限调度实验。

- R08_CONTROL.asc：已15/15 Pass的R08原样副本，用来观察本轮波动。
- R09_RESIDUAL_PACKETS.asc：在R08上将残余大K的GM输出也按四块成包，降低握手次数。
- R10_SINGLE_WAVE_GRID.asc：独立从R08派生，仅调整每核恰好一个任务的宏块网格。

用户确认R07点5运行TLE，根因尚未确定。R10去掉R07逐任务搜索且保持原任务轮数，
不能称已验证修复。R09不含这项调度实验，两版都保留R08小K输出协议，不互相包含。

最新T5为1.90μs，同T复算R04 34.276579、R05 34.579701、R06 34.105836、R08 34.808289。
R08点13/14有正向观测，仍缺同版相邻控制，不能认定稳定提速。保存每次15点与当次T，
按前后控制逐点对照，不全局比例校正、不拼接逐点最低耗时。TLE需记录点号、阶段与报错文字。

每版444次普通源码CPU运行、222对重复输出通过，三版输出逐位一致；6758组网格和
25088项尾块公式核对通过，两项故障注入被捕获。仍有原3项极端数值限制。
未本地CANN编译或NPU测试，R09/R10待平台验证，CPU结果不是硬件性能或正确性认证。

R09残余ring由64KiB增到256KiB/核组，片上内存不变；短流首包等待可能抵消收益。
R10增加N分片时partial归约也增加，峰值工作量下降不等于同倍数提速。

SHA256：

{hashes}

MANIFEST与CPU_CHECKS绑定同一源码。完整设计/检查器/平台反馈随CANN仓库归档。
''')
    write(ROOT/'README.md','''# BatchMatmulMaxSum：R08通过，推进R09/R10

用户确认R08为15/15 Pass；R07在点5运行阶段TLE，根因未确定。
按最新T5=1.90μs复算：R04 34.276579，R05 34.579701，R06 34.105836，R08 34.808289。
R08点13/14改善值得复核，仍未排除波动；暂作开发父版，历史R04保留。

- [提交包：R08控制、R09、R10](BMMS_V11_R09_R10_提交包.zip) / [使用说明](BMMS_V11_R09_R10/README.md)
- [当前审计](BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [R07/R08反馈与原图](V11_results/2026-09-26_r07_r08_submission/AUDIT.md)
- [本轮设计](V11_recovery/DESIGN.md) / [CPU检查](V11_recovery/CHECKS.json)
- [R07主机开销诊断](V11_recovery/R07_HOST_DIAGNOSIS.json) / [独立网格核对](V11_recovery/GRID_CHECKS.json)
- [上轮交付状态](audit_current/AUDIT_R07_R08_DELIVERY.md)

R09扩展残余大K的四块输出成包；R10单独验证闭式单任务网格。两版均从R08独立派生。
先R08→R09→R08，再R10→R08；每次整体替换官方code/kernel.asc，保存完整15点和T。
R10不是已经证实的TLE修复。每版444次普通CPU运行通过，仍有3项既有极端数值限制；
本地未CANN编译/NPU测试，候选待平台结果。

```bash
python V11_recovery/build.py
python V11_recovery/diagnose_r07.py
python V11_recovery/run_checks.py
python V11_recovery/update_docs.py
python V11_recovery/package.py
```

归档：[CANN/v11](https://github.com/Pengyiyan0411/CANN/tree/v11/BMMS)。
历史文档保留交付当时状态，最新结论以当前审计和结果记录为准。
''')
    write(HERE/'CANN_README.md','''# CANN

BatchMatmulMaxSum算子代码、平台反馈和审计证据归档，当前位于v11分支。
用户明确确认R08为15/15 Pass；R07点5运行阶段TLE，尚未确认根因。
按最新T5=1.90μs复算R08为34.808289，R04为34.276579。单次观测不代表已排除波动。

下一轮R09扩展残余大K四块输出成包，R10以闭式单任务网格替代R07逐任务搜索；
两版从R08独立派生。附字节相同的R08控制，先R08→R09→R08，再R10→R08。

- [提交包](BMMS/BMMS_V11_R09_R10_提交包.zip) / [使用说明](BMMS/BMMS_V11_R09_R10/README.md)
- [当前审计](BMMS/BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [R07/R08结果](BMMS/V11_results/2026-09-26_r07_r08_submission/AUDIT.md)
- [设计](BMMS/V11_recovery/DESIGN.md) / [检查证据](BMMS/V11_recovery/CHECKS.json)
- [归档SHA清单](BMMS/ARCHIVE_MANIFEST.json) / [复现说明](BMMS/README.md)

R08/R09/R10各444次普通源码CPU运行通过，6758组网格及25088项尾块公式核对通过。
两个故障注入被捕获。原3项极端数值限制保留；本地无CANN/NPU验证，R09/R10平台待测。
R10不标记为已修复TLE。历史源码、ZIP、原图和交付时文档保持原样。
''')
    print('Current audit, R08-controlled submission notes and history snapshot updated.')
if __name__=='__main__':main()

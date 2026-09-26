"""Refresh delivery documents without rewriting frozen earlier submissions."""
from pathlib import Path
import hashlib
import json
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / 'BMMS_V11_R05_R06'


def write(path, text):
    path.write_text(text, encoding='utf-8', newline='\n')


def main():
    result = json.loads((ROOT / 'V11_results/2026-09-26_r04_submission/RESULT.json').read_text(encoding='utf-8'))
    scores = result['scores_same_current_T']
    checks = json.loads((HERE / 'CHECKS.json').read_text(encoding='utf-8'))
    manifest = json.loads((OUT / 'MANIFEST.json').read_text(encoding='utf-8'))
    assert checks['ordinary_outputs_equal_bitwise']
    assert all(row['rejected'] for row in checks['negative_controls'].values())
    for row in manifest['variants']:
        assert hashlib.sha256((OUT / row['file']).read_bytes()).hexdigest() == row['sha256'] == checks['sources'][row['file']]
    audit = ROOT / 'BatchMatmulMaxSum_当前审计报告_2026-09-26.md'
    snapshot = ROOT / 'audit_current/AUDIT_R04_DELIVERY.md'
    if not snapshot.exists():
        assert 'R04合并待提交' in audit.read_text(encoding='utf-8')
        shutil.copyfile(audit, snapshot)
    score_table = '\n'.join(f'| {name} | {value:.6f} |' for name, value in scores.items())
    points = '\n'.join(f'| {r["case"]} | {r["R02_us"]:.2f} | {r["R03_us"]:.2f} | {r["R04_us"]:.2f} | {r["T_us"]:.2f} |'
                       for r in result['rows'] if r['case'] in [7,8,9,10,11,12,13,15])
    write(audit, f'''# BatchMatmulMaxSum 当前审计：R04反馈与R05/R06底层优化

2026-09-26。本轮截图15/15 Pass，按唯一前序交付归属R04；用户写“SOTA”但未再次标注
文件名，未获得平台源hash。该归属依据明确记录在结果文件中。本轮完成两项独立优化、
离线检查和可提交源码，未自行提交比赛平台，未使用NPU测试环境。

## 当前判断

R04保留了R02点9–12与R03点7/15的收益，当前记录内同口径得分最高。
这支持继续宏块输入复用和宏块发布路线。本轮进一步压缩Cube指令和重复归约，
不扩大路由、不更改核数规划。R04继续作为保底；R05和R06都是独立的R04后继。

| 版本 | 同本轮T复算分数 |
|---|---:|
{score_table}
| R05 / R06 | 待平台反馈 |

点9的T由51.78变为51.77μs，表内历史耗时均按最新T复算。
公式为`mean(100/(1+ln(time/T)/ln(1.5)))`，本轮较R02增加
{scores['R04_contextual'] - scores['R02']:.6f}分。未核验全榜排名，“当前最好”仅指已有记录。
界面0.00%是舍入显示；没有重复计时，不对小幅变化给出统计显著性结论。

## 平台反馈

| 点 | R02 μs | R03 μs | 本轮/R04 μs | T μs |
|---|---:|---:|---:|---:|
{points}

点9–12与R02相差约0.2%–0.4%；点15为35.76μs，保留R03的主要收益。
点8仍约5.34倍T，点13约3.63倍T，点12仍慢于P01历史108.87μs。
因此整体瓶颈尚未全部解决。缺少hidden shape和profiler，不能按耗时倒推精确路由，
也不能声称下面任一改动必然改善某个隐藏点。
完整截图、15点和来源说明见 [本轮结果](V11_results/2026-09-26_r04_submission/AUDIT.md)。

## 两项独立实现

| 候选 | 实际改动 | 预期作用及代价 |
|---|---|---|
| R06_MACRO_MMAD | 改L0输入布局，四次64×128 MMAD合为一次128×256；短轴LoadData循环；Fixpipe按完整宏块NZ步长切片 | 减少Cube调用与地址循环；资源及GM字节数保持父版 |
| R05_DEFERRED_MAX | 128列lane max跨全部N面板保留，最后归约；完整C块跳过清填 | 减少重复行归约、清填及相关手工fence；UB峰值增加 |

R06仅改宏块生产者；R05改宏块和原生小K/残余共享消费者。两版都保留公开shape
分派、FP32全K累加、max N后sum M、GM ring及其READY/FREE协议。
R06不含R05，R05不含R06。详细地址公式、同步说明与官方接口依据见
[设计](V11_lowlevel/DESIGN.md)；源码差异保存为两个diff。

在B1/M128/N256/K256/cores1的控制例，R06的MMAD API调用16→4、LoadData 64→32；
GM输入196608B、L0输入196608B、C写131072B均不变。三个宽N控制例中，
R05行归约调用降到父版1/4。这些是CPU源码模型中的调用计数，不是设备耗时或提速倍数。

R05最大UB申请181280B（微块消费者，M8192），低于模型192KiB容量；
宏块消费者最大148000B。R06资源与R04相同，L1/L0A/L0B/L0C分别
393216/32768/65536/131072B。实际编译器分配和硬件执行仍待平台验证。

## 本地证据与边界

| 检查 | 结果 |
|---|---|
| 普通源码CPU运行 | R04/R05/R06各256次，精度失败0，普通输出记录三版逐位相同 |
| 重复运行 | 每版128对输出逐位核对 |
| 调度 / guard | 每版4494 / 7560项 |
| 覆盖 | 四布局、双dtype、负数/零、同时M/N/K尾块、M8192、跨槽复用、N分片、K32/64/128原生路径 |
| 尾块负向检查 | 故意跳过R05尾N清填，被未初始化UB检查拒绝 |
| 排布负向检查 | 故意将R06 Fixpipe源步长写成微块M，产生错误输出并被拒绝 |
| 既有数值限制 | 每版3次FP32消去/BF16中间溢出限制仍复现，未宣称修复 |
| CANN / NPU | 未在本地编译 / 未在本地运行 |

检查执行实际抽取的生产/消费计算源码，但不是Ascend硬件仿真，也不编译完整CANN ABI。
R06的实际Cube舍入和R05的设备队列依赖需由平台确认。检查与源码SHA绑定见
[CHECKS.json](V11_lowlevel/CHECKS.json)。未将平台15点Pass推广为全数值域正确性证明。

## 交付与后续

先提交 [R06_MACRO_MMAD.asc](BMMS_V11_R05_R06/R06_MACRO_MMAD.asc)，再独立提交
[R05_DEFERRED_MAX.asc](BMMS_V11_R05_R06/R05_DEFERRED_MAX.asc)。每次整体替换官方
`code/kernel.asc`，入口和官方main/CMake维持原状。完整比较15点和T列后，再决定是否合并。

[提交包](BMMS_V11_R05_R06_提交包.zip) / [使用说明](BMMS_V11_R05_R06/README.md)。
原R04源码和ZIP保持原SHA。之前的交付状态见 [R04交付快照](audit_current/AUDIT_R04_DELIVERY.md)。
全部代码与结果归档在 [CANN/v11](https://github.com/Pengyiyan0411/CANN/tree/v11/BMMS)，
本地推送与核验状态见ARCHIVE_STATUS.json。本轮继续利用平台提交反馈，暂不需要申请测试环境。
''')
    hashes = '\n'.join(f'- `{r["file"]}`：`{r["sha256"]}`' for r in manifest['variants'])
    write(OUT / 'README.md', f'''# R05 / R06 提交说明

两版分别从冻结的R04派生，互不包含。建议提交顺序：

1. **R06_MACRO_MMAD.asc**：整宏块MMAD、重排L0输入并合并LoadData；只改宏块生产者。
2. **R05_DEFERRED_MAX.asc**：N扫描结束再归约行最大值，完整C块跳过清填；改两类消费者。

每次选择一份`.asc`整体替换官方`code/kernel.asc`。入口仍为题目规定的`run_kernel`，
不改官方main/CMake，不额外设置ASCENDC_CUBE_ONLY，不手动拼接两版。
请按对应R05/R06保留平台全部15点、T列；若编译或精度失败，保留完整日志。

本轮R04截图15/15 Pass，按最新T复算{scores['R04_contextual']:.6f}，为现有记录最好。
用户仅标“SOTA”，R04归属依据唯一前序交付；平台源hash未提供。
该成绩不是R05/R06的成绩，两版均待平台编译、正确性和性能反馈。

R04/R05/R06各256次普通源码CPU运行通过，每版128对重复输出核对，普通输出记录逐位相同。
调度4494项、guard7560项；故意破坏尾N清填和L0C步长均被检查捕获。
原有3个极端数值限制仍复现。CPU模型不是硬件仿真；本地未CANN编译、未NPU测试。

在128×256、K256控制例，R06 MMAD调用16→4、LoadData64→32；三个宽N控制例中
R05行归约调用降到1/4。以上仅为源码API计数，不能当作设备提速比例。
R05微块消费者UB峰值181280B，GM workspace维持R04。两版保留既有路由及FP32点积。

父版SHA256：`{manifest['base_sha256']}`。

{hashes}

MANIFEST.json与CPU_CHECKS.json记录相同源码SHA；完整设计和差异见仓库V11_lowlevel目录。
''')
    write(ROOT / 'README.md', f'''# BatchMatmulMaxSum：R04反馈后推进R05/R06

本轮截图15/15 Pass，按唯一前序交付归属R04，同最新T复算{scores['R04_contextual']:.4f}，
当前记录内最好。R04同时保留R02大点及R03点15的收益，继续冻结为保底。

两份独立候选已准备好：先提交 [R06_MACRO_MMAD.asc](BMMS_V11_R05_R06/R06_MACRO_MMAD.asc)，
再提交 [R05_DEFERRED_MAX.asc](BMMS_V11_R05_R06/R05_DEFERRED_MAX.asc)。前者合并整宏块
Cube指令和L0搬运，后者复用N方向lane max并减少完整C块清填；每次整体替换官方`code/kernel.asc`。

- [提交包](BMMS_V11_R05_R06_提交包.zip) / [使用说明](BMMS_V11_R05_R06/README.md)
- [当前审计](BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [R04截图与同T结果](V11_results/2026-09-26_r04_submission/AUDIT.md)
- [本轮设计](V11_lowlevel/DESIGN.md) / [源码CPU检查](V11_lowlevel/CHECKS.json)
- [冻结R04源码](BMMS_V11_R04/R04_MACRO_RING_RESIDUAL.asc) / [历史交付快照](audit_current/AUDIT_R04_DELIVERY.md)

三版各256次普通源码CPU运行通过，普通输出记录逐位一致，两个负向检查被正确拒绝。
原有3个极端数值限制保留；未CANN编译/未运行NPU，R05/R06实际成绩待平台反馈。
模型中的指令调用减少不代表同倍数提速。用户暂无环境，继续平台提交。

```bash
python V11_lowlevel/build.py
python V11_lowlevel/run_checks.py
python V11_lowlevel/update_docs.py
python V11_lowlevel/package.py
```

归档：[CANN/v11](https://github.com/Pengyiyan0411/CANN/tree/v11/BMMS)。
历史交付文档保留当时状态，最新结论以当前审计及结果记录为准。
''')
    write(HERE / 'CANN_README.md', f'''# CANN

BatchMatmulMaxSum算子开发归档，当前路线和证据位于`v11`分支。
本轮截图15/15 Pass，按唯一前序候选归属R04；同最新T复算{scores['R04_contextual']:.4f}，
为当前记录内最好成绩，未核验全榜排名。原R04源码与ZIP冻结保存。

新候选分别从R04派生：先提交
[R06_MACRO_MMAD.asc](BMMS/BMMS_V11_R05_R06/R06_MACRO_MMAD.asc)，再提交
[R05_DEFERRED_MAX.asc](BMMS/BMMS_V11_R05_R06/R05_DEFERRED_MAX.asc)。
R06合并整宏块MMAD并改L0排布，R05复用N方向lane max并减少C块清填。两版互不包含。

- [提交包](BMMS/BMMS_V11_R05_R06_提交包.zip) / [使用说明](BMMS/BMMS_V11_R05_R06/README.md)
- [当前审计](BMMS/BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [R04反馈截图与结果](BMMS/V11_results/2026-09-26_r04_submission/AUDIT.md)
- [本轮设计](BMMS/V11_lowlevel/DESIGN.md) / [离线检查](BMMS/V11_lowlevel/CHECKS.json)
- [归档SHA清单](BMMS/ARCHIVE_MANIFEST.json) / [复现说明](BMMS/README.md)

R04/R05/R06各256次普通源码CPU运行通过，两个负向检查捕获预期错误。
原有3个极端数值限制保留；R05/R06未在本地CANN编译或NPU测试，实际平台成绩待反馈。
源码API计数下降不作为设备耗时预测。v9/v10分支及BMMS内历史交付文件保留原始状态。
''')
    print('Updated current audit, submission instructions and repository readmes; old R04 delivery preserved.')


if __name__ == '__main__':
    main()

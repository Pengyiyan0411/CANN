"""Publish current status while retaining the previous delivery-time audit."""
from pathlib import Path
import importlib.util
import json
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / 'BMMS_V11_R04'


def write(path, text):
    path.write_text(text, encoding='utf-8', newline='\n')


def main():
    result = json.loads((ROOT / 'V11_results/2026-09-26_r02_r03_submission/RESULT.json').read_text(encoding='utf-8'))
    scores = result['scores_same_current_T']
    checks = json.loads((HERE / 'CHECKS.json').read_text(encoding='utf-8'))
    manifest = json.loads((OUT / 'MANIFEST.json').read_text(encoding='utf-8'))
    assert checks['source_sha256'] == manifest['sha256']
    audit = ROOT / 'BatchMatmulMaxSum_当前审计报告_2026-09-26.md'
    snap = ROOT / 'audit_current/AUDIT_R02_R03_DELIVERY.md'
    if not snap.exists():
        shutil.copyfile(audit, snap)
    table = '\n'.join(f'| {name} | {scores[name]:.6f} |' for name in ['P01_historical','D01','F01','R01','R02','R03'])
    points = '\n'.join(f'| {r["case"]} | {r["R01_us"]:.2f} | {r["R02_us"]:.2f} | {r["R03_us"]:.2f} | {r["T_us"]:.2f} |'
                       for r in result['rows'] if r['case'] in [7,8,9,10,11,12,13,15])
    write(audit, f'''# BatchMatmulMaxSum 当前审计：R02/R03通过，R04合并待提交

2026-09-26。用户明确标注R02、R03均15/15 Pass。用户暂无测试环境，继续采用
本地离线检查和平台多次提交。本轮完成结果归档、R04实现及提交包，未自行提交比赛平台。

## 当前判断

**保留宏块复用路线，并合并两项分别获得正向反馈的改动。**
R02改善点9–12，R03大幅改善点15；两版收益互补。当前同T复算最高的已确认候选是R02。
R04仅合并宏块发布与公开shape残余域，没有叠加新的tile、核数或算术改动。

| 版本 | 同本轮T复算分数 |
|---|---:|
{table}
| R04 | 待平台反馈 |

新截图点9的T从52.01变为51.78μs；本表将所有历史耗时按新T统一计算，
R01因此从旧口径31.853562变为{scores['R01']:.6f}，原始历史记录保留。
R02较R01增加{scores['R02']-scores['R01']:.6f}分，R03增加{scores['R03']-scores['R01']:.6f}分。
平台源hash、hidden shape和profiler未提供；归属来自用户明确标注。
0.00%是界面舍入显示。不同提交没有重复测量，不能给出统计显著性。

## 性能证据

| 点 | R01 μs | R02 μs | R03 μs | 本轮T μs |
|---|---:|---:|---:|---:|
{points}

- R02点9–12较R01耗时降低9.43%–13.20%，支持保留宏块发布机制。
- R03点15由115.13降至37.08μs，约3.10倍；点7由13.82降至10.85μs。
  点9–12接近R01，符合两项独立实验的预期。没有隐藏shape，不能声称已直接观测其路由。
- 点12的R02结果仍慢于P01历史108.87μs；点8和点13也仍有明显差距。
  本次进展不等于主要性能问题全部解决，下一项优化等合并版结果后再定。

完整15点与截图见 [R02/R03结果审计](V11_results/2026-09-26_r02_r03_submission/AUDIT.md)。
F01整体退化后恢复P01专用分支，R01引入真实输入复用但总分未胜P01；
R02/R03分别验证输出发布和覆盖差异，R04承接这两项，历史未改写。

## R04实现与检查

入口为R02宏块→R03残余D01→原P01。新增残余域明确排除R02Eligible，
各自分配workspace：宏块ring256KiB/核组、残余64KiB/核组；运行时只成功启动一个路径。
完整保留R02正文，R03片段仅修改Eligible引用的命名空间。旧源码和ZIP保持原SHA。

| 本地检查 | 结果 |
|---|---|
| 普通源码CPU运行 | 173次，精度失败0；88次重复位模式核对 |
| 调度 / guard边界 | 4494 / 7560 |
| 对比旧R03 | 84条已有输出记录逐位一致 |
| 合并路由覆盖 | 98次宏块、78次残余；包含3次已知限制调用 |
| 交替核数1/20/1/20 | 两种路径和两种ring尺寸正确切换，退出credit清空 |
| 同步负向检查 | 故意提前FREE被环槽所有权检查拒绝 |
| 极端数值 | 原有3个消去/中间溢出限制仍复现 |
| 本地CANN / NPU | 未编译 / 未运行 |

模型执行实际抽取的device计算代码及分派条件，未编译完整AscendC ABI，不认证硬件
缓存、实际指令舍入或性能。R04未取得平台结果，不能把父版本Pass算作R04已通过。
不按隐藏点号分派，不将逐点最快成绩拼成合并版成绩。

## 下一次提交

提交 [R04_MACRO_RING_RESIDUAL.asc](BMMS_V11_R04/R04_MACRO_RING_RESIDUAL.asc)，
整体替换官方`code/kernel.asc`，其他官方文件保持原样。
[提交ZIP](BMMS_V11_R04_提交包.zip) / [说明](BMMS_V11_R04/README.md) /
[设计](V11_merge/DESIGN.md) / [检查证据](V11_merge/CHECKS.json)。

验收重点是15/15 Pass后，点9–12是否保留R02水平、点15是否保留R03水平，
同时检查其他点和完整总分；不保证耗时机械叠加。暂不需要申请测试环境。

旧交付审计见 [R02/R03交付快照](audit_current/AUDIT_R02_R03_DELIVERY.md)、
[R01交付快照](audit_current/AUDIT_R01_DELIVERY.md)，更早历史见audit_current。
代码与结果归档到 [CANN/v11](https://github.com/Pengyiyan0411/CANN/tree/v11/BMMS)，
本地推送与文件核验状态在ARCHIVE_STATUS.json。
''')
    write(OUT / 'README.md', f'''# R04_MACRO_RING_RESIDUAL 提交说明

本版合并用户确认15/15 Pass的R02宏块发布与R03残余域分支。
**提交文件：`R04_MACRO_RING_RESIDUAL.asc`**，整体替换官方`code/kernel.asc`。
入口仍为题目规定的`run_kernel`；不改main/CMake，不额外设置ASCENDC_CUBE_ONLY。

源SHA256：`{manifest['sha256']}`。

R02原有输入复用、宏块发布及P01回退正文保留；仅接入互斥的R03残余分支。
GM ring分别为256KiB/核组与64KiB/核组，两条路径使用各自workspace。
没有增加新的调参或数值特判，也没有按平台测试编号分派。

本地173次普通源码CPU运行、4494个调度和7560个guard检查通过；
84条已有R03输出记录逐位一致，交替路由和提前FREE负向检查通过。
原有3个极端数值限制仍存在。本地无CANN/NPU，**R04尚未平台编译/正确性/性能验证**。

请将本次结果标为R04，保留全部15点和T列；目标是同时保持R02点9–12与R03点15的收益。
源文件、MANIFEST和CPU_CHECKS对应同一SHA，不要再次手动拼接R02/R03。

R02/R03按最新T复算分别{scores['R02']:.6f}/{scores['R03']:.6f}，R01为{scores['R01']:.6f}。
这些是独立父版本的成绩，不是R04性能预测。点9的T已变为51.78μs。
''')
    write(ROOT / 'README.md', f'''# BatchMatmulMaxSum：R02/R03反馈后提交R04

R02、R03均由用户确认15/15 Pass。同最新T复算：R02 {scores['R02']:.4f}，
R03 {scores['R03']:.4f}，R01 {scores['R01']:.4f}，P01历史{scores['P01_historical']:.4f}。
R02改善点9–12；R03点15降至37.08μs，点7也改善。

下一次提交 [R04_MACRO_RING_RESIDUAL.asc](BMMS_V11_R04/R04_MACRO_RING_RESIDUAL.asc)：
合并上述两项，不叠加新调参。整体替换官方`code/kernel.asc`。
[提交包](BMMS_V11_R04_提交包.zip) / [提交说明](BMMS_V11_R04/README.md)。

- [当前审计](BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [R02/R03原图、逐点耗时及同T得分](V11_results/2026-09-26_r02_r03_submission/AUDIT.md)
- [R04设计](V11_merge/DESIGN.md) / [CPU检查证据](V11_merge/CHECKS.json)
- [冻结R02/R03](BMMS_V11_R02_R03/README.md) / [R01结果](V11_results/2026-09-26_r01_submission/AUDIT.md)

R04本地173次普通源码CPU运行通过，已知3个极端数值限制保留。
未CANN编译/未运行NPU；父版本Pass不代表R04已通过。用户暂无环境，继续平台提交。

```bash
python V11_merge/build.py
python V11_merge/run_checks.py
python V11_merge/update_docs.py
python V11_merge/package.py
```

归档：[CANN/v11](https://github.com/Pengyiyan0411/CANN/tree/v11/BMMS)。
历史交付文档保留当时状态，最新结论以当前审计及结果记录为准。
''')
    write(HERE / 'CANN_README.md', f'''# CANN

BatchMatmulMaxSum算子开发归档，当前路线和证据位于`v11`分支。
用户已确认R02/R03均15/15 Pass；按最新T复算R02 {scores['R02']:.4f}、R03 {scores['R03']:.4f}。

当前待提交候选：[R04_MACRO_RING_RESIDUAL.asc](BMMS/BMMS_V11_R04/R04_MACRO_RING_RESIDUAL.asc)，
合并R02宏块发布和R03互斥残余分支，整体替换官方`code/kernel.asc`。

- [R04提交包](BMMS/BMMS_V11_R04_提交包.zip) / [使用说明](BMMS/BMMS_V11_R04/README.md)
- [当前审计](BMMS/BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [R02/R03截图与结果](BMMS/V11_results/2026-09-26_r02_r03_submission/AUDIT.md)
- [R04设计](BMMS/V11_merge/DESIGN.md) / [离线检查](BMMS/V11_merge/CHECKS.json)
- [归档文件SHA清单](BMMS/ARCHIVE_MANIFEST.json) / [复现说明](BMMS/README.md)

R04已完成173次普通源码CPU运行与分支、环槽检查，未CANN编译/未NPU运行，
原有3个极端数值限制保留。R04的实际平台性能待反馈，不拼接历史最短耗时作为成绩。
旧源码、结果和交付快照保留在BMMS目录与历史提交，v9/v10分支继续保存相应历史版本。
''')


if __name__ == '__main__':
    main()

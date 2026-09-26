"""Record the new observed baseline and the two reduced-launch experiments."""
from pathlib import Path
import hashlib,json,subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;OUT=ROOT/'BMMS_V11_R13_R14'
PREVIOUS='f6f597b62759d9327a4d00306a940d1bf2e98cf2';AUDIT='BatchMatmulMaxSum_当前审计报告_2026-09-26.md'
def write(p,s):p.write_text(s,encoding='utf-8',newline='\n')
def main():
    result=json.loads((ROOT/'V11_results/2026-09-26_r11_r12_submission/RESULT.json').read_text(encoding='utf-8'))
    checks=json.loads((HERE/'CHECKS.json').read_text(encoding='utf-8'))
    manifest=json.loads((OUT/'MANIFEST.json').read_text(encoding='utf-8'))
    assert checks['ordinary_outputs_equal_bitwise'] and all(x['rejected'] for x in checks['negative_controls'].values())
    for row in [manifest['control'],*manifest['variants']]:
        assert hashlib.sha256((OUT/row['file']).read_bytes()).hexdigest()==row['sha256']==checks['sources'][row['file']]
    old=subprocess.check_output(['git','show',PREVIOUS+':BMMS/'+AUDIT],cwd=ROOT/'CANN_archive')
    snapshot=ROOT/'audit_current/AUDIT_R11_R12_DELIVERY.md'
    if not snapshot.exists():snapshot.write_bytes(old)
    assert snapshot.read_bytes()==old
    scores='\n'.join(f'| {k} | {v:.6f} |' for k,v in result['scores_same_current_T'].items())
    points='\n'.join(f'| {r["case"]} | {r["R10_us"]:.2f} | {r["R11_us"]:.2f} | {r["R12_us"]:.2f} | {r["T_us"]:.2f} | {r["R11_vs_R10_time_delta_pct"]:+.2f}% |' for r in result['rows'])
    write(ROOT/AUDIT,f'''# BatchMatmulMaxSum 当前审计：采用R11，推进R13/R14

2026-09-26。用户明确标注图1是R12、图2是R11，均15/15 Pass。
R11点11出现明显正向变化，暂作下一轮开发基线；R12不合并。两版只有一次逐点观测，
未获得相邻R10控制或重复样本；本轮不声称R11已经复测稳定。R10继续冻结作为回退版本。

## 结果：统一T后比较

| 版本 | 按本轮同一T复算分数 |
|---|---:|
{scores}

T6为7.23→7.09、T8为17.32→14.88、T13为5.21→5.20、T14为7.09→5.40μs。
历史图的原始耗时保持原样，仅在本表用同一T复算分数。上轮R10的36.170754与本次分数
不能直接横比；本次同T下R10为35.553080，R11为36.937232，增加1.3842分。

| 点 | R10 μs | R11 μs | R12 μs | 本次T μs | R11对R10耗时变化 |
|---|---:|---:|---:|---:|---:|
{points}

R11点11为135.77→100.71μs，耗时下降25.82%；同轮R12点11为135.49μs。
R11点10为83.75μs，保留了R10的84.10μs水平。其他小变化先记为未分辨，不从单张图
制造每点提速结论，不全局缩放去噪、不拼接最短点。0.00%只是误差栏显示。
[原图、完整测量和源码SHA绑定](V11_results/2026-09-26_r11_r12_submission/AUDIT.md)。

## 迭代判断

- R10单轮网格：用户上轮明确确认稳定收益，保留。
- R11消除短第二轮：本轮点11有约25.8%改善，15/15 Pass，作为工作基线，稳定性待复核。
- R12并行N合并：没有显示同量级收益，当前不合并其额外GM缓冲和同步。

两次有效改动都只改变host网格，支持继续优化核间负载。没有hidden shape或profiler，
不能判定各点的具体形状、分支或硬件瓶颈；也不能据此认定N归约在所有输入上都不重要。
R09收益不明显的定性记录、R07点5运行TLE且根因未知的记录均保留。

## 下一版：允许少量核不启动

R11以全核因数网格为限制，部分输入仍有尾轮或过大的分片。R13/R14均完整保留R11作为
fallback，只在使用至少75%可用核且三个峰值工作量均下降至少12.5%时改成较少核的一轮任务。
这是工作量筛选规则，不是性能保证或噪声阈值。

| 候选 | 相对R11的独立作用域 | 例子 |
|---|---|---|
| R13_FLEX_SHORT_WAVE | 只调整R11剩余的多轮计划，保留所有已有单轮决策 | B8/M4096/N4096/K256、20核：24任务/20核→16任务/16核，峰值宏块352→256 |
| R14_FLEX_SINGLE_WAVE | 只调整R11已有单轮计划，保留全部多轮计划 | B1/M384/N1792/K256、8核：8任务/8核→7任务/7核，峰值宏块4→3 |

例子均为合成输入，不对应隐藏测评点。两版device源码、所有guard、原生小K和残余路径
均与R11一致，没有新同步或scratch；实际启动、ring申请和消费者步长统一使用新blocks。
每核UB/L1/L0不增加，但pN变化可能改变partial空间和N归约成本。

最多69个候选，逐候选闭式评估；新增部分对旧多轮计划仅遍历一次。若R11本身已遍历旧
计划，R13会再做一次，未误称整体仅一次。没有恢复R07逐候选逐任务的搜索。
较少核可能降低聚合带宽，收益仍需平台验证；R13覆盖较广优先提交，R14是较窄的独立实验。
[设计、代价与官方核数依据](V11_flexible_grid/DESIGN.md) / [host微基准](V11_flexible_grid/HOST_BENCH.json)。

## 验证状态

| 检查 | 本轮结果 |
|---|---|
| 普通源码CPU执行 | R11/R13/R14各464次，普通精度失败0，三版输出逐位一致 |
| 重复运行 | 每版232对输出核对通过 |
| 实际缩小launch | R13有8次、R14有4次源码执行触发，含多batch与尾块 |
| 原调度 / guard | 每版4494 / 7560项通过 |
| 独立网格检查 | 8272组合法形状；R13改变1112组，R14改变34组，作用域互斥 |
| 独立穷举oracle | 42次，不使用被测峰值公式选优 |
| 故障注入 | 保留旧blocks、漏最后一个task，两种错误均被拒绝 |
| 隔离末段归约 | 每版22次原串行归约检查通过 |
| 片上峰值 | UB 132256、L1 393216、L0A 32768、L0B 65536、L0C 131072字节，三版相同 |
| 既有数值限制 | 每版3项FP32消去/BF16中间溢出限制仍复现，未宣称全域精度达标 |
| CANN / NPU | 本地未执行；R11/R12有平台Pass，R13/R14待提交 |

[CHECKS.json](V11_flexible_grid/CHECKS.json)绑定源码和检查器SHA。CPU模型不能验证设备
cache、流水、舍入与耗时；没有把离线检查当作NPU认证。本轮没有消耗卡时。

## 提交与归档

建议 **R11_CONTROL → R13 → R11_CONTROL → R14 → R11_CONTROL**；先提交R13即可。
每份asc独立整体替换官方code/kernel.asc，沿用官方main/CMake，不手动叠加。
保存完整15点与当次T，用相邻R11控制逐点比较；边界附近的变化再复测。

[提交包](BMMS_V11_R13_R14_提交包.zip) / [使用说明](BMMS_V11_R13_R14/README.md)。
[上轮交付状态快照](audit_current/AUDIT_R11_R12_DELIVERY.md)保留当时待反馈的结论。
源码、反馈、原图、检查器和包归档至[CANN/v11](https://github.com/Pengyiyan0411/CANN/tree/v11/BMMS)，
实际推送记录见本地ARCHIVE_STATUS.json。所有历史源码和提交包冻结保留。
''')
    hashes='\n'.join(f'- `{r["file"]}`：`{r["sha256"]}`' for r in [manifest['control'],*manifest['variants']])
    write(OUT/'README.md',f'''# R13 / R14提交包：附原样R11控制

先提交 **R13_FLEX_SHORT_WAVE.asc**，再独立测试 **R14_FLEX_SINGLE_WAVE.asc**。
建议穿插控制：R11_CONTROL → R13 → R11_CONTROL → R14 → R11_CONTROL。
每次选择一份asc整体替换官方`code/kernel.asc`，沿用main/CMake，不手动合并，
不添加ASCENDC_CUBE_ONLY。两份候选都独立从R11派生，未包含R12。

- R11_CONTROL.asc：已15/15 Pass的R11原样副本，点11为100.71μs；目前只有一次逐点观测。
- R13：只消除R11剩余的多轮任务，允许少量核不启动，保留已有单轮决策。
- R14：只改R11已经单轮的布局，测试略少核、更均衡的网格，作用域与R13互斥。

候选至少使用75%可用核，最忙核的宏块数、C元素数和输入长度均下降至少12.5%才采用。
最多69个候选，闭式评估；device、原生小K、残余路径和guard均不变，无新增同步或scratch。
较少核可能降低聚合带宽，pN变化也可能增加归约成本，结构改善不保证设备提速。

统一本次T后：R10 35.553080、R11 36.937232、R12 35.618585。T6/8/13/14均变化，
不要直接用上一轮总分作比较。R11作为工作基线，R12暂不合并；R11稳定性仍待复核。
保留每次15点与T，按相邻R11控制逐点比较，不拼接最佳点、不全局比例校正。

每版464次普通源码CPU执行、232对重复及22次隔离归约检查通过，普通输出三版逐位一致。
8272组网格、42次独立穷举检查通过，两项规划故障被捕获。原3项极端精度限制仍保留。
本地未CANN编译/NPU测试，R13/R14尚无平台结果；R07点5运行TLE根因仍未确定。

SHA256：

{hashes}

MANIFEST及CPU_CHECKS绑定相同源码。完整设计、差异、检查器和平台反馈随CANN/v11归档。
''')
    write(ROOT/'README.md','''# BatchMatmulMaxSum：R11工作基线，R13/R14待测

图1明确为R12、图2为R11，均15/15 Pass。R11点11为100.71μs，相对R10下降25.82%，
点10保持83.75μs。R11作为工作基线，R12不合并；本轮仅单次观测，尚无重复控制统计。
使用最新同一T复算：R10 35.553080、R11 36.937232、R12 35.618585。

- [提交包：R11控制、R13、R14](BMMS_V11_R13_R14_提交包.zip) / [使用说明](BMMS_V11_R13_R14/README.md)
- [当前审计](BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [R11/R12反馈及原图](V11_results/2026-09-26_r11_r12_submission/AUDIT.md)
- [设计](V11_flexible_grid/DESIGN.md) / [CPU检查](V11_flexible_grid/CHECKS.json)
- [独立网格审计](V11_flexible_grid/GRID_CHECKS.json) / [host微基准](V11_flexible_grid/HOST_BENCH.json)
- [上轮交付状态](audit_current/AUDIT_R11_R12_DELIVERY.md)

R13只改剩余多轮，R14只改已有单轮；均允许少量核不启动以降低最忙核工作量。
先R11→R13→R11，再R14→R11；每次整体替换官方code/kernel.asc，保留main/CMake。

三版各464次普通CPU执行、232对重复、22次隔离归约检查通过。8272组网格核对，
42次独立穷举和两项故障注入通过。既有3项极端精度限制未修复，本地无CANN/NPU验证。
R07点5运行TLE根因未知。候选未取得平台结果，不能将工作量估计当作性能保证。

```bash
python V11_flexible_grid/build.py
python V11_flexible_grid/audit_plans.py
python V11_flexible_grid/run_checks.py
python V11_flexible_grid/bench_plans.py
python V11_flexible_grid/update_docs.py
python V11_flexible_grid/package.py
```

归档：[CANN/v11](https://github.com/Pengyiyan0411/CANN/tree/v11/BMMS)。历史文件保持交付时状态，
以当前审计和对应结果目录为最新结论。update_docs.py归档历史时需要CANN_archive checkout。
''')
    write(HERE/'CANN_README.md','''# CANN

BatchMatmulMaxSum算子源码、平台反馈和审计证据，位于v11分支。
R11/R12均15/15 Pass；R11点11降至100.71μs，点10保持83.75μs，成为工作基线。
同本次T复算R10/R11/R12为35.553080/36.937232/35.618585。R12暂不合并。
本轮每版只有一次逐点截图，R11尚未获得重复稳定性确认。

R13/R14独立从R11派生，允许至少75%可用核的较少核启动，分别处理剩余多轮/已有单轮。
device源码未改；先R11→R13→R11，再R14→R11，使用本次T及相邻控制比较。

- [提交包](BMMS/BMMS_V11_R13_R14_提交包.zip) / [使用说明](BMMS/BMMS_V11_R13_R14/README.md)
- [当前审计](BMMS/BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [R11/R12反馈](BMMS/V11_results/2026-09-26_r11_r12_submission/AUDIT.md)
- [设计](BMMS/V11_flexible_grid/DESIGN.md) / [检查证据](BMMS/V11_flexible_grid/CHECKS.json)
- [源码SHA清单](BMMS/ARCHIVE_MANIFEST.json) / [复现说明](BMMS/README.md)

各版464次普通源码CPU运行通过，8272组网格、42次独立穷举和两项规划故障注入通过。
既有3项极端数值限制保留，本地无CANN/NPU验证；R13/R14待平台结果。R07运行TLE根因未知。
历史源码、ZIP、原图和当时的交付文档保持原样。
''')
    print('R11 baseline audit, R13/R14 notes and frozen historical snapshot updated.')
if __name__=='__main__':main()

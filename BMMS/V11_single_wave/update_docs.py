"""Publish R10 feedback and R11/R12 delivery without rewriting frozen evidence."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;OUT=ROOT/'BMMS_V11_R11_R12'
PREVIOUS='44a67cc33ebdbee620904de5f03681a244216d5a'
AUDIT='BatchMatmulMaxSum_当前审计报告_2026-09-26.md'
def write(p,s):p.write_text(s,encoding='utf-8',newline='\n')
def main():
    result=json.loads((ROOT/'V11_results/2026-09-26_r09_r10_submission/RESULT.json').read_text(encoding='utf-8'))
    checks=json.loads((HERE/'CHECKS.json').read_text(encoding='utf-8'))
    manifest=json.loads((OUT/'MANIFEST.json').read_text(encoding='utf-8'))
    assert result['evidence']['R10']['user_reports_stable_benefit']
    assert checks['ordinary_outputs_equal_bitwise'] and all(v['rejected'] for v in checks['negative_controls'].values())
    for row in [manifest['control'],*manifest['variants']]:
        assert hashlib.sha256((OUT/row['file']).read_bytes()).hexdigest()==row['sha256']==checks['sources'][row['file']]
    snapshot=ROOT/'audit_current/AUDIT_R09_R10_DELIVERY.md'
    old=subprocess.check_output(['git','show',PREVIOUS+':BMMS/'+AUDIT],cwd=ROOT/'CANN_archive')
    if not snapshot.exists():snapshot.write_bytes(old)
    assert snapshot.read_bytes()==old
    scores='\n'.join(f'| {k} | {v:.6f} |' for k,v in result['scores_same_current_T'].items())
    points='\n'.join(f'| {r["case"]} | {r["R08_us"]:.2f} | {r["R10_us"]:.2f} | {r["T_us"]:.2f} | {r["R10_vs_R08_time_delta_pct"]:+.2f}% |' for r in result['rows'])
    write(ROOT/AUDIT,f'''# BatchMatmulMaxSum 当前审计：R10成为工作基线，推进R11/R12

2026-09-26。用户明确反馈R09没有明显收益，R10收益稳定且明显；典型R10截图15/15 Pass。
采纳用户的复测判断，以R10作为工作基线。R09不合并；R11/R12均已实现，从R10独立派生。
当前没有CANN/NPU测试环境，本轮继续交付平台提交包。

## 结果与证据

| 版本 | 使用本次同一T复算分数 |
|---|---:|
{scores}

R10典型总分比R08高1.3656分。T14从7.10变为7.09μs，所有表内历史分数已按最新T
统一复算；没有改写历史截图或旧记录。R09只有定性反馈，没有逐点时延、分数和通过点数。

| 点 | R08 μs | R10典型 μs | 最新T μs | R10对R08耗时变化 |
|---|---:|---:|---:|---:|
{points}

点10的106.62→84.10μs为主要收益，耗时下降21.12%，约1.268倍速度。其他多点接近
历史波动幅度，点15本图更慢，均保留原值。完整分数使用这张图全部15点，未拼接最佳值。
稳定性来自用户复测结论；目前归档只有一张定量截图，没有完整重复样本或置信区间。
不因此否定用户的观察，也不虚构统计检验结果。0.00%是页面误差栏显示，不能证明位级相同。
[原始截图、逐点数据与版本绑定](V11_results/2026-09-26_r09_r10_submission/AUDIT.md)。

## 路线判断

R10与R08的device实现一致，只改宏块host网格；这轮稳定收益说明任务分配方向值得
继续。R09的残余大K成包没有明显收益，停止合并该实验。没有hidden shape或profiler，
不能声称已确定点10的形状或流水瓶颈，也不能从R10通过推断R07点5TLE的根因。

| 候选 | 相对R10的改动 | 明确的代价与验证目标 |
|---|---|---|
| R11_SINGLE_WAVE_EXPAND | 将符合条件的短第二轮任务压成一轮，保留R10已有单轮决策 | 多一次很小的host评估；pN增加可能增大partial归约 |
| R12_PARALLEL_N_MERGE | 按行块把N分片Max合并分给多个AIV，最后仍完整M向量求和 | 额外GM读写和一次全局同步，验证串行归约是否值得并行 |

R11不改device源码，核数不增加。旧任务只遍历一次，最多126项；候选仅限一轮因数网格，
三个最忙核工作量都下降至少12.5%才采用。6758组独立网格核对，154组在R10上进一步改变。
合成B1/M1024/N1024/K256、20核组由8×3/24任务改为5×4/20任务，峰值宏块3→2；
R10已选好的B1/M4096/N4096、20核组5×4保持不变。不能把这些合成例子当作隐藏测试点。

R12仅在pN≥4且M≥1024时并行N合并；每128行一个job，所有AIV参加第二同步。
原partial不覆盖，额外scratch为B*M float；所有宏块启动均额外申请该空间，上界2MiB。
完整M ReduceSum调用和输入顺序保留，避免分块求和改变结合顺序。没有增加UB/L1/L0。
隔离末段B1/M1024/pN4、20核组例，峰值读取4096→1536个float，但总读取4096→5120，
并额外写1024个float及增加一次同步，因此不能把峰值下降直接当作整体提速。

[完整设计及官方接口依据](V11_single_wave/DESIGN.md) / [host微基准](V11_single_wave/HOST_BENCH.json)。

## 验证状态

| 检查 | 结果 |
|---|---|
| 普通源码CPU执行 | R10/R11/R12各452次，失败0，普通输出三版逐位一致 |
| 重复运行 | 每版226对输出检查通过 |
| 原调度 / guard | 每版4494 / 7560项通过 |
| 独立网格枚举 | 6758组，154组新增改变；唯一覆盖、峰值及全局总量通过 |
| 隔离归约 | 每版22次；R12中14次并行、8次关闭，通过所有权/覆盖/原数据保护检查 |
| 故障注入 | 删除第二同步、漏最后一个N分片，分别被检查器捕获 |
| 片上峰值 | UB 132256、L1 393216、L0A 32768、L0B 65536、L0C 131072字节，三版相同 |
| 既有极端数值限制 | 每版3项FP32消去/BF16中间溢出限制仍复现 |
| CANN编译 / NPU | 本地未执行；R10有平台Pass，R11/R12待平台结果 |

[CHECKS.json](V11_single_wave/CHECKS.json)绑定源码和检查器SHA。CPU模型用于存储、
覆盖和协议审查，不能代替设备流水、cache、舍入和性能验证。没有宣称全输入域精度达标。
R07用户确认点5运行阶段TLE，根因仍未知，历史记录和源码冻结保留。

## 提交与归档

建议 **R10_CONTROL → R11 → R10_CONTROL → R12 → R10_CONTROL**，可先只提交R11。
每份asc单独整体替换官方code/kernel.asc，main/CMake沿用官方文件，不手动合并。
保存每次完整15点和当次T；对照前后R10逐点判断，不全局比例校正，不拼接最佳点。
接近控制波动范围的变化先记为未分辨，有明确收益后再合并独立改动。

[提交包](BMMS_V11_R11_R12_提交包.zip) / [使用说明](BMMS_V11_R11_R12/README.md)。
[上轮交付审计快照](audit_current/AUDIT_R09_R10_DELIVERY.md)保留当时待反馈状态。
归档目标[CANN/v11](https://github.com/Pengyiyan0411/CANN/tree/v11/BMMS)，实际推送记录
见本地ARCHIVE_STATUS.json。历史源码、ZIP、截图和结果原样保留。
''')
    hashes='\n'.join(f'- `{r["file"]}`：`{r["sha256"]}`' for r in [manifest['control'],*manifest['variants']])
    write(OUT/'README.md',f'''# R11 / R12提交包：附原样R10控制

先测 **R11_SINGLE_WAVE_EXPAND.asc**，再单独测 **R12_PARALLEL_N_MERGE.asc**。
建议顺序：R10_CONTROL → R11 → R10_CONTROL → R12 → R10_CONTROL。
每次选一份asc整体替换官方`code/kernel.asc`，沿用官方main/CMake，不手动叠加，
不加ASCENDC_CUBE_ONLY。两份候选均独立从R10派生，不包含R09。

- R10_CONTROL.asc：用户已确认收益稳定、15/15 Pass的R10字节相同副本。
- R11：保留R10已有单轮网格，仅消除符合条件的短第二轮任务，不改device源码。
- R12：宏块路径按行块并行合并N分片，最后仍执行原完整M ReduceSum；不改R10网格。

R10典型点10为84.10μs，R08为106.62μs，下降21.12%。本次同T复算总分R10为
36.170754、R08为34.805192。用户报告收益稳定，但只有一张逐点原图，未虚构重复统计。
R09仅有“没啥收益”的定性反馈，未伪造时延或通过数。R07点5运行TLE根因未确认。

本轮R10/R11/R12各452次普通源码CPU执行、226对重复运行和22次隔离归约检查通过；
6758组网格核对通过，两项故障注入被捕获。普通输出三版逐位一致，3项既有极端数值
限制仍然存在。本地未CANN编译或NPU测试，R11/R12尚未取得平台结果。

R11可能增加N分片带来的partial成本。R12所有宏块启动额外申请B*M*4字节GM
（上界2MiB）；并行gate开启时增加GM读写和一次AIV全局同步，可能抵消并行收益。
UB/L1/L0不增加。CPU模型不能证明硬件时延与流水正确性。

保留每次完整15点及当次T，和相邻R10控制逐点比较；波动范围内先不认定收益，
不全局比例修正，不拼接各版最短点。若TLE，记录点号、运行/编译阶段和报错文字。

SHA256：

{hashes}

MANIFEST和CPU_CHECKS绑定相同源码；完整设计、检查器、原始反馈随CANN/v11归档。
''')
    write(ROOT/'README.md','''# BatchMatmulMaxSum：R10工作基线，R11/R12待提交

用户确认R10收益稳定且明显；典型点10为84.10μs，比R08下降21.12%，15/15 Pass。
同最新T复算R10为36.170754，R08为34.805192。R09没有明显收益，不合并。

- [提交包：R10控制、R11、R12](BMMS_V11_R11_R12_提交包.zip) / [使用说明](BMMS_V11_R11_R12/README.md)
- [当前审计](BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [R09/R10反馈及原图](V11_results/2026-09-26_r09_r10_submission/AUDIT.md)
- [设计及代价](V11_single_wave/DESIGN.md) / [CPU检查](V11_single_wave/CHECKS.json)
- [网格核对](V11_single_wave/GRID_CHECKS.json) / [host微基准](V11_single_wave/HOST_BENCH.json)
- [上轮交付状态](audit_current/AUDIT_R09_R10_DELIVERY.md)

R11消除符合条件的短第二轮任务，R12独立并行N分片合并，两者都保留R10已有效的改动。
先R10→R11→R10，再R12→R10；每次只选一个asc整体替换官方code/kernel.asc。
保存全部15点与当次T，逐点比相邻控制，避免把小波动当收益。

每版452次普通CPU执行、226对重复和22次隔离归约检查通过，两个故障注入被捕获。
既有3项极端精度限制仍在；本地未CANN编译/NPU验证，候选待测。R07点5运行TLE根因未知。

```bash
python V11_single_wave/build.py
python V11_single_wave/run_checks.py
python V11_single_wave/bench_plans.py
python V11_single_wave/update_docs.py
python V11_single_wave/package.py
```

归档：[CANN/v11](https://github.com/Pengyiyan0411/CANN/tree/v11/BMMS)。历史文档保持交付时状态，
最新结论以当前审计及对应结果记录为准。update_docs.py归档历史时需要本地CANN_archive checkout。
''')
    write(HERE/'CANN_README.md','''# CANN

BatchMatmulMaxSum代码、平台结果与审计证据，当前位于v11分支。
R10已15/15 Pass，用户确认收益稳定；典型点10从R08的106.62降至84.10μs。
同最新T复算R10为36.170754、R08为34.805192。R10成为工作基线，R09不合并。

下一轮R11消除短第二轮任务，R12并行N分片合并；两版独立从R10派生，附原样R10控制。
先R10→R11→R10，再R12→R10，记录每次15点及当次T，保留完整测评波动。

- [提交包](BMMS/BMMS_V11_R11_R12_提交包.zip) / [使用说明](BMMS/BMMS_V11_R11_R12/README.md)
- [当前审计](BMMS/BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [R09/R10反馈及原图](BMMS/V11_results/2026-09-26_r09_r10_submission/AUDIT.md)
- [设计](BMMS/V11_single_wave/DESIGN.md) / [检查证据](BMMS/V11_single_wave/CHECKS.json)
- [归档SHA清单](BMMS/ARCHIVE_MANIFEST.json) / [复现说明](BMMS/README.md)

各版452次普通源码CPU执行、22次隔离归约及6758组网格核对通过，两个故障注入被捕获。
原3项极端数值限制未修复；本地无CANN/NPU验证，R11/R12待平台测试。R07点5运行TLE根因未知。
历史源码、ZIP、原图和交付时文档保留原样；稳定收益为用户复测报告，未伪造统计样本。
''')
    print('R10 baseline audit and independent R11/R12 submission notes written.')
if __name__=='__main__':main()

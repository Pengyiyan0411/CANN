from pathlib import Path
import json,zipfile,hashlib,statistics as st
ROOT=Path(__file__).resolve().parents[1];D=ROOT/'V12_npu_lab/results/split_20260928';R=D/'evidence/results'
s=json.loads((D/'SUMMARY.json').read_text());a=json.loads((R/'split_analysis.json').read_text())
screen=json.loads((R/'split_r12_screen_summary.json').read_text())['summary']
table=[]
for r in screen:
    _,B,M,N,K,dt,ta,tb=r['case'];old=r['baseline_median_us'];new=r['candidate_median_us']
    table.append(f'| {M}×{N}×{K} | {old:.3f} | {new:.3f} | {100*(1-new/old):.1f}% |')
event=[]
for key,label in [('split_r12_event_alllayouts1','64样本全布局，第1进程'),('split_r12_event_alllayouts2','64样本全布局，第2进程'),
                  ('split_r12_event_holdout','50额外尺寸，第1进程'),('split_r12_event_holdout_repeat','50额外尺寸，第2进程'),
                  ('split_r12_event_aa','同版本A/A，8样本')]:
    r=s['event_summary'][key]
    event.append(f"| {label} | {r['gain_pct_min']:.3f}% | {r['gain_pct_median']:.3f}% | {r['gain_pct_max']:.3f}% |")
controls=json.loads((R/'split_r12_routes_repeat_summary.json').read_text())['summary']
ct=[]
for r in controls:
    i,B,M,N,K,dt,ta,tb=r['case'];x=r['baseline_median_us'];y=r['candidate_median_us']
    ct.append(f'| {i}: B{B}, {M}×{N}×{K}, dt{dt}, {ta}{tb} | {x:.3f} | {y:.3f} | {100*(y/x-1):+.2f}% |')
dot=R/'split_r12_dot_control_summary.json'
assert dot.exists(),'Finish the targeted dot comparison before packaging.'
dr=json.loads(dot.read_text())['summary'][0]
dot_note=f"另对 FP16 短 Dot 单独复查4个交替窗口，每次80调用丢弃前20次：r03各窗口中位数为 {dr['baseline_medians_us']} μs，r12为 {dr['candidate_medians_us']} μs；总体中位数 {dr['baseline_median_us']:.3f}→{dr['candidate_median_us']:.3f} μs。"
body='''# Case15：r10 / r11 / r12 上卡实验

本轮推荐提交 **v12_r12_splitk_adaptive_merge.asc**。比赛主线仍为冻结 r03，待用户真实15点反馈后再决定晋升。用户明确回报 r07 的实际收益被噪声淹没，已将其状态改为不晋升。

## 结论与三轮消融

| 版本 | 改动 | 结论 |
|---|---|---|
| r10 | 整 K 分片一次进入L1，容量允许范围内扩大L0 K块；原单AIV消费 | 收益混合，额外尺寸中最差约退化6%，不单独交付 |
| r11 | 原生产端仅改紧凑N写出；每AIV负责8完整行的K合并/N max，再同步M sum | 大M/多分片的合并成本明显下降；部分小M接近零收益 |
| r12 | r11合并端；N≤64或TB时使用整分片生产端，其余保留原分段流水 | 本轮最值得提交的候选；全布局及额外尺寸均独立复测 |

新分派要求原 Split-K eligible，且 B=1、M≤64、N≤128、MN≤4096、原S≥8。与历史L04/L05/L06证据一致。没有精确shape假定，也没有测试编号、输入内容或历史输出参与分派。删除新增模块和唯一入口后，r03字节完全恢复。

每个K分片的起止位置、S、blocks保持不变。消费者先对同一元素完成所有K分片相加，然后对真实N做max，最后对M求和。8行拥有者写出互不重叠的32B行最大值；所有AIV参加两个屏障，最终只有worker0输出。新增workspace为M×4，最多256B。

## 性能：所有以下数据都是合成样本

实际设备为 Ascend910_9362、20 Cube核，CANN9.0.0，编译架构沿用Judge工程dav-2201。隐藏Case15精确shape、dtype、转置和计时契约仍未知。不能把下表直接称为比赛Case15成绩。

轻量msprof任务时间，FP16 NN、B=1；每进程每例40次、丢弃前10次，A/B/B/A四进程。表中数值是两个进程中位数再取中位数。

| M×N×K | r03 μs | r12 μs | 缩短 |
|---|---:|---:|---:|
'''+ '\n'.join(table)+'''

辅助设备事件测试在同一进程、相同已分配输入/workspace上交替真实kernel调用；每窗口64次、首轮100次热身、窗口前8次预热。全布局每例12对窗口，其他组20对。两个独立进程复测如下；这衡量设备流吞吐，包含提交间隙，排除了公开入口的分配/释放，不能与msprof时间或Judge未知口径直接混用。

| 组别 | 最小缩短 | 各样本缩短中位数 | 最大缩短 |
|---|---:|---:|---:|
'''+ '\n'.join(event)+'''

64样本是8个几何尺寸×2种精度×4种转置；50额外样本覆盖25组M/N和另外两个K值，未用作首轮参数筛选。首轮出现的约-0.022%和额外样本复测约-0.076%落在本轮A/A扰动量级，不能把近零值宣传成稳定收益。中位收益是这批合成样本的统计，不是总榜分数或真实Case15收益。

## 正确性与内存/竞争检查

'''+f"r12 **{s['precision']['r12']['cases']}/{s['precision']['r12']['cases']} 个输入用例通过，每例3次，共{s['precision']['r12']['calls']}次**。其中128例长K簇和守卫边界，100例既有回归集，10例原有路线对照。覆盖FP16/BF16、四转置、K尾块、零值、负值、宽动态范围、相同列、批量与形状守卫外输入。\n\n"+'''每次公开入口测试前将输出填入NaN。参考基于真实量化后的输入，以CPU FP64计算完整matmul→N max→M sum，要求有限输出且满足 `abs(error)≤1e-4+1e-4*abs(reference)`。'''+f"最大误差/容差比 {s['precision']['r12']['max_tolerance_ratio']:.9f}；性能窗口另验证复用workspace后的结果。\n\n"+'''
主机资源/地址检查覆盖183825个计划，整分片L1≤320KiB，L0A/L0B各≤64KiB；并行消费端显式UB最多65824B。50组M/N/S整数模型验证K求和、有效地址和每行唯一拥有者。它们不是异步硬件证明。

mssanitizer普通构建运行了FP16 TT的64×64×4096和48×80×6112两个边界用例，输出验证通过。memcheck未报告ERROR，但检测范围有限，并有48条FFTS_BASE_ADDR复位警告。**2026-09-28 Case8复查更正：racecheck日志虽有No error detected，但也明确写了缺少--cce-enable-sanitizer并暂时跳过，不能计为竞争检测通过。** 原结论误读了日志；原始数据保留。尚未在原Case15样本上完成有效插桩race/init/sync验收；r12主线接受依据为用户实际Judge反馈。

## 其他路径：保留源码并实际复查

6个紧邻守卫的对照均通过。另覆盖短Dot、微矩阵、batch Native、residual、真正命中Case8 padded guard的两例、R06长K、Native dense/narrow。第一次2窗口中一组候选进程整体偏慢，随后增加5窗口交替复查；以下保留完整结果，不用源代码相同代替性能证据。正的变化表示更慢。

| 对照输入 | r03 μs | r12 μs | 时间变化 |
|---|---:|---:|---:|
'''+ '\n'.join(ct)+ '\n\n'+dot_note+'''

其他大矩阵/Native对照的首次统一变慢未在后五窗口稳定复现；短Dot专项复查为1.000→0.995 μs，先前偏慢也未复现。短Dot的绝对时间对热身和测量上下文敏感，不能跨测量组直接比较。此处不承诺所有未知测试点绝对不退化，实际提交仍需完整15点核对。

## 下一方向

先提交r12验收Case15，r03保留回退。之后优先Case8：在真正命中R43域的合成簇里拆清输入整理、pack-to-Cube等待和计算/消费成本，再决定是否做panel整理与Cube重叠。R45去清零和R46 SDK路线已失败，不重试同一假设。Case2作备用；Case13/9/10暂停已失败的微调；Case6需先定位route。详细步骤见 [NEXT_DIRECTIONS.md](../../../BMMS_V12/NEXT_DIRECTIONS.md)。

## 复现与证据

- [SUMMARY.json](SUMMARY.json)：精度计数、源文件/二进制hash、事件统计、守卫外对照、sanitizer状态。
- [split_results.zip](split_results.zip)：原始JSONL、CSV、测试manifest/seed/输入hash、构建和检测日志。大输入和可执行程序保留在远端 `/home/developer/bmms_v12_lab_20260928`。
- 生成器：`V12_impl_r10/build.py`、`V12_impl_r11/build.py`、`V12_impl_r12/build.py`；主机检查在r10/prepare.py、r11/check.py。
- 测试脚本：`V12_npu_lab/harness/generate_split.py`、`generate_split_controls.py`、`run_split_r12.sh`、`validate_split_final.sh`、`run_screen.py`。
- 运行前source实际CANN9.0.0环境；cmake需显式传入BMMS_VERSIONS包含r03/r12，构建bench_r12和event_bench_r12。所有NPU任务串行，计时不与编译/其他NPU任务并发。

SHA256：

```text
'''+f"r03 {s['source_binary_hashes']['r03.asc']}\nr12 {s['source_binary_hashes']['r12.asc']}\n"+'''```
'''
(D/'REPORT.md').write_text(body,encoding='utf-8')
readme='''# v12_r12：Case15 提交候选

提交完整单文件 `v12_r12_splitk_adaptive_merge.asc`。已确认比赛主线仍是 `v12_baseline_r03.asc`；r12等待真实15点反馈。

改动：只在Case15已确认的元数据范围启用8行一个向量核的K分片合并；N≤64或B转置时将完整K分片一次搬入L1，其余保留原生产流水。先完整K求和，再N max，最后M sum；不改变S和K分区。旧路径源码逐字节保留。

实际CANN编译通过；238个合成输入、每例3次全部通过。64个全布局样本两轮设备事件计时中位缩短21.53%/21.87%，50个额外尺寸两轮为17.92%/17.55%；部分小M形状接近零收益。这些不是比赛Case15成绩。普通构建memcheck未报告ERROR且有已记录的FFTS警告；racecheck因缺少插桩被工具跳过，不能计为通过（Case8复查已更正旧表述）。

建议与r03交替提交，记录全部15点；确认Case15可重复收益和其他点表现后再晋升。r10有退化不推荐，r11保留为结构对照。

- [详细实验报告](../V12_npu_lab/results/split_20260928/REPORT.md)
- [下一方向](NEXT_DIRECTIONS.md)：优先Case8阶段成本分析；Case2备用，Case6先定位route。
- [版本身份](v12_r12_manifest.json)

源码SHA256：`'''+s['source_binary_hashes']['r12.asc']+'`\n'
(ROOT/'BMMS_V12/v12_r12_README.md').write_text(readme,encoding='utf-8')
for v,summary in [('r10','整K分片生产端；实测收益混合，不推荐单独提交。'),('r11','原生产端加并行合并；有效，作为r12的独立结构对照。')]:
    (ROOT/f'BMMS_V12/v12_{v}_README.md').write_text(f'# v12_{v}：Case15结构实验\n\n{summary}\n\n[完整报告](../V12_npu_lab/results/split_20260928/REPORT.md)。主线仍为r03。\n',encoding='utf-8')
with zipfile.ZipFile(ROOT/'BMMS_V12/v12_r12_case15_submission.zip','w',zipfile.ZIP_DEFLATED) as z:
    for name in ['v12_r12_splitk_adaptive_merge.asc','v12_r12_manifest.json','v12_baseline_r03.asc','NEXT_DIRECTIONS.md']:
        z.write(ROOT/'BMMS_V12'/name,name)
    z.writestr('v12_r12_README.md',readme.replace('../V12_npu_lab/results/split_20260928/REPORT.md','REPORT.md'))
    z.writestr('REPORT.md',body.replace('../../../BMMS_V12/NEXT_DIRECTIONS.md','NEXT_DIRECTIONS.md'))
    for name in ['SUMMARY.json','split_results.zip']:z.write(D/name,name)
print('Wrote REPORT.md, README files and submission archive.')

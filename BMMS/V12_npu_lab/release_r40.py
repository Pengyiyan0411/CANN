from pathlib import Path
import hashlib
import json
import zipfile

root = Path(__file__).resolve().parents[1]
v = root / 'BMMS_V12'
out = root / 'V12_npu_lab/results/r40_20260929'
out.mkdir(exist_ok=True)

def read(p):
    return json.loads(p.read_text(encoding='utf-8'))

def write(p, d):
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

with zipfile.ZipFile(out / 'r40_evidence.zip') as z:
    assert z.testzip() is None
    hashes = json.loads(z.read('manifest.json'))['files']
    for name, expected in hashes.items():
        assert hashlib.sha256(z.read(name)).hexdigest() == expected, name
    for name in z.namelist():
        assert not Path(name).is_absolute() and '..' not in Path(name).parts
    z.extractall(out / 'evidence')

summary = read(out / 'evidence/results/r40_summary.json')
assert summary['all_pass'] and summary['precision_configurations'] == 166 and summary['precision_calls'] == 498
source = v / 'v12_r40_probe_r37_unchanged_in_domain.asc'
digest = hashlib.sha256(source.read_bytes()).hexdigest()
assert source.read_bytes() == (out / 'evidence/r40.asc').read_bytes()
assert hashlib.sha256((v / 'v12_baseline_r33.asc').read_bytes()).hexdigest() == '86debd5c403af4bb436d6c042de4530faf05637cf6fd1aeaae6ed6b410d11d80'
assert (v / 'v12_baseline_r33.asc').read_bytes() == (out / 'evidence/r33.asc').read_bytes()

previous = root / 'V12_npu_lab/results/r39_20260929/evidence/results'
old_rows, new_rows = {}, {}
for suffix in ['correctness', 'extra_correctness']:
    for line in (previous / f'r39_{suffix}.jsonl').read_text().splitlines():
        r = json.loads(line)
        old_rows[r['case']] = r
    for line in (out / f'evidence/results/r40_{suffix}.jsonl').read_text().splitlines():
        r = json.loads(line)
        new_rows[r['case']] = r
assert old_rows.keys() == new_rows.keys()
assert not any(r['r40_hit'] and old_rows[i]['r39_hit'] for i, r in new_rows.items())
summary['r39_r40_hit_sets_disjoint_on_166_configurations'] = True
summary['evidence_files_sha256_verified'] = len(hashes)

cal = summary['calibration']
hits = sum(x['hit'] for x in cal)
misses = len(cal) - hits
assert hits > 0 and misses > 0 and summary['hit_ratio_range'][0] > 5
assert all(r['block_num'] == ['1'] and r['mix_block_num'] == ['2'] for r in summary['profiler_launch'] if r['hit'])
write(out / 'SUMMARY.json', summary)

table = '\n'.join(
    f"|{r['case'][0]}|{'×'.join(map(str, r['case'][2:5]))}|{r['case'][5]} / {r['case'][6]},{r['case'][7]}|{'HIT' if r['hit'] else 'MISS'}|{r['r33_us']:.3f}|{r['r40_us']:.3f}|{r['ratio']:.3f}×|"
    for r in cal
)
hr = summary['hit_ratio_range']
mr = summary['miss_ratio_range']
report = f'''# r39反馈与r40互补诊断

主线保留 **v12_r33**；r37没有证实Judge收益，r39/r40都是诊断文件，不晋升为性能基线。本次只交付r40一个待测文件。

## r39最新反馈

用户截图全15点Pass、显示误差0.00%，Case11 **97.35 μs**、Case12 **114.93 μs**，均无压力信号。版本按对r39交付的直接回复归属，截图没有版本/SHA标签。这支持r39谓词为FALSE，即未发生其检测的计划切换；不能独自区分前置条件未满足和域内计划相同。其余点的小幅变化不认定为诊断版本优化收益。

完整15点数据和原图见 `V12_results/2026-09-29_r39_feedback`。此前r39本地HIT校准10.78～13.67倍，正常耗时不是已校准的HIT状态。

## 为什么追加这一条

r37要求最重核的宏块数严格减少，且最重核的元素量、输入量不增加才改计划，适用范围内也有大量原样返回的形状。因此目前既不能宣称队友范围错误，也不能把r37构造样本上的改善推广到隐藏点。

r40谓词：`r30完整路由条件 && cores>=2 && r37::InDomain && 新旧(pM,pN,tasks,blocks)完全相同`。完整路由条件包括dtype、Eligible、AlignedPitch和Family筛选；明确保留InDomain，避免简单取反把域外形状也错误标成命中。

InDomain使用队友给出的两个区间：

- Case11候选域：B=1，1536≤M<1792，2048≤N<3072，2048≤K<2560。
- Case12候选域：B=1，1280≤M<1536，4096≤N<6144，1536≤K<1664。

还需满足原路由的M/N 16对齐、K 32对齐及pitch条件；这些区间没有被当作已知精确shape。

命中后使用既有r30设备内核、`pM=pN=blocks=1,tasks=B`执行完整运算并重新计算workspace；未命中回到r33正常分派。没有新设备入口、没有额外kernel循环、没有省略算术。正常r30和r33的MakePlan没有改成r37版本。相对r39只有诊断模块的guard、比较条件、命名及分派入口改变，反向替换可逐字节恢复r39。

## NPU校准结果

Ascend910_9362、20 Cube、CANN9.0.0、dav-2201。完整构建通过，166组构造配置×3次，共498次数值检查全部通过，其中{summary['hit_configurations']}组HIT。覆盖FP16/BF16、四种布局、零/全负/尺度变化/重复列、域外和已有优化路径。参考为量化输入上的CPU FP64，每输出容差`1e-4+1e-4*abs(ref)`，每次NaN填充输出。最大误差/容许误差比{summary['max_tolerance_ratio']:.9f}。166组r39/r40的命中集合交集为空。

选{len(cal)}组（{hits} HIT、{misses} MISS）运行公共入口msprof；两版各两个独立进程，按A/B、B/A顺序，30次丢弃前5次，每调用1个kernel。命中倍率 **{hr[0]:.2f}～{hr[1]:.2f}×**；未命中 **{mr[0]:.3f}～{mr[1]:.3f}×**。所有HIT在profiler中实际为Block Num=1、Mix Block Num=2。这里的构造样本编号不是比赛case编号，dtype 1=FP16，2=BF16。

|构造样本|M×N×K|dtype / ta,tb|判定|r33 μs|r40 μs|倍率|
|---|---|---|---|---:|---:|---:|
{table}

这些时间用于确认信号可分，不用于预测隐藏case绝对延时；它们是设备task time，也不覆盖Judge计时协议差异。

## Judge判读与后续

11/12分别判读：

|r39|r40|含义与下一步|
|---|---|---|
|正常|显著变慢且Pass|满足完整guard及新范围，但r37选择原计划。后续查实际分割和同等宏块数下的成本，停止继续只改“严格减宏块数”的策略。|
|正常|仍正常|未满足r40完整条件。结合r39支持未切换，优先核对新范围/路由条件；不能仅凭此指出具体哪一维错误。|
|正常|Fail或中间态|不解码，先检查提交版本、正确性或计时异常。|

结合本地校准，约5倍以上且Pass可作为保守强HIT信号，轻微涨跌不算HIT。此诊断不会带来排名收益，测完回到r33。若核数、版本或数据集发生变化，不能直接与前一次拼接解码。

本轮复用已有设备代码，未重复全指令sanitizer；历史r33的race/init问题尚未闭环，不宣称安全检测全部通过。最初远程脚本因Windows CRLF退出，修正为LF后重跑；没有影响源码hash或最终校准。

源SHA256：`{digest}`。`r40_evidence.zip`内{len(hashes)}个文件的SHA及ZIP CRC已核验，包含实际源码、构建日志、输入生成器/seed/hash、数值结果、原始profiler CSV及二进制SHA。
'''
(out / 'REPORT.md').write_text(report, encoding='utf-8')

readme = f'''# v12_r40：r37域内未切换计划探针

**仅诊断，主线仍为r33。** 按上一张图为r39判读，11/12=97.35/114.93μs，均未出现压力信号。

提交文件：`{source.name}`。r40仅在满足r37完整适用条件且新旧计划相同时，以单组完成真实计算来放大耗时。

- 显著变慢且Pass：进入目标范围，但r37没有换计划；下一步调整计划选择成本或设备流水。
- 仍约正常耗时：结合r39，优先复核新范围和路由条件。
- Fail或模糊中间态：不作形状/计划推断。11和12独立判断。

完整编译通过；166配置、498次数值检查全Pass；{hits}个HIT和{misses}个MISS经公开入口profiler校准，HIT {hr[0]:.2f}～{hr[1]:.2f}倍、MISS {mr[0]:.3f}～{mr[1]:.3f}倍。所有HIT实际1 Cube+2 Vector。可用约5倍以上且Pass识别强信号，勿把轻微波动当成命中。这是构造样本校准，不是隐藏测试的绝对时间预测。

无新增设备入口；未命中执行r33原路径，r33源码hash保持不变。历史sanitizer未决项沿用，没有宣称全量安全检测通过。

详细记录：[REPORT.md](../V12_npu_lab/results/r40_20260929/REPORT.md)。

SHA256：`{digest}`。
'''
(v / 'v12_r40_README.md').write_text(readme, encoding='utf-8')

manifest = read(v / 'v12_r40_manifest.json')
assert manifest['sha256'] == digest
manifest.update(status=f'NPU full build and 166x3 precision passed; {hits} HIT/{misses} MISS profiler calibration passed; pending Judge diagnostic only',
    report='../V12_npu_lab/results/r40_20260929/REPORT.md', precision_configurations=166, precision_calls=498,
    hit_calibration_ratio_range=hr, miss_calibration_ratio_range=mr,
    r39_r40_hit_sets_disjoint_on_166_configurations=True)
write(v / 'v12_r40_manifest.json', manifest)
main = read(v / 'MAINLINE.json')
assert main['accepted_sota'] == 'v12_baseline_r33.asc'
old = main.get('active_diagnostic')
if old and old['version'] != 'v12_r40' and not any(x['version'] == old['version'] for x in main['historical_diagnostics']):
    old['historical'] = True
    main['historical_diagnostics'].append(old)
main['active_diagnostic'] = dict(version='v12_r40', file=source.name, sha256=digest, parent='v12_baseline_r33.asc',
    purpose=manifest['predicate'], status=manifest['status'], readme='v12_r40_README.md', historical=False)
main['next_action'] = 'Submit r40 only: distinguish unchanged plans inside the full r37 optimization domain from unmet guards/domain; judge11/12 independently. Keep r33 baseline.'
main['latest_experiment_report'] = '../V12_npu_lab/results/r40_20260929/REPORT.md'
main['recommended_candidate'] = None
write(v / 'MAINLINE.json', main)
feedback = read(root / 'V12_results/2026-09-29_r39_feedback/RESULTS.json')
summary39 = read(root / 'V12_npu_lab/results/r39_20260929/SUMMARY.json')
summary39['judge_feedback'] = feedback
summary39['next_diagnostic'] = 'v12_r40'
write(root / 'V12_npu_lab/results/r39_20260929/SUMMARY.json', summary39)

for version, src in [('r39', v / 'v12_r39_probe_r37_plan_change.asc'), ('r40', source)]:
    with zipfile.ZipFile(v / f'v12_{version}_submission.zip', 'w', zipfile.ZIP_DEFLATED) as z:
        for p in [src, v / f'v12_{version}_README.md', v / f'v12_{version}_manifest.json']:
            z.write(p, p.name)
    with zipfile.ZipFile(v / f'v12_{version}_submission.zip') as z:
        assert z.testzip() is None and z.read(src.name) == src.read_bytes()
print(json.dumps(dict(status='r40 ready; r33 unchanged', hits=hits, misses=misses, hit_range=hr, miss_range=mr, verified_files=len(hashes))))

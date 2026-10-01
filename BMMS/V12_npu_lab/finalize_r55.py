from pathlib import Path
import csv, hashlib, json, statistics, zipfile

root=Path(__file__).resolve().parents[1];v=root/'BMMS_V12';out=root/'V12_npu_lab/results/r55_coverage_20261001'
raw=out/'evidence'
check=[json.loads(s) for s in (raw/'results/r55_correctness.jsonl').read_text().splitlines()]
assert len(check)==164 and all(s['pass'] and s['repeats']==3 for s in check)
perf=json.loads((raw/'results/r55_calibration_summary.json').read_text())
control=json.loads((root/'V12_npu_lab/results/case12_k1_20261001/evidence/results/r54_screen_summary.json').read_text())
src=v/'v12_r55_probe_r54_full_gate.asc';digest=hashlib.sha256(src.read_bytes()).hexdigest()
assert perf['source_sha256']['r55']==digest
assert (raw/'r55.asc').read_bytes()==src.read_bytes()
assert (raw/'r41.asc').read_bytes()==(v/'v12_baseline_r41.asc').read_bytes()
assert len(perf['summary'])==32
# Prior full r54 C-ABI execution supplies the observed target-kernel labels.
label={}
for r in control['runs']:
    if r['version']=='r54':
        hit=any('bmms1254_' in k for k in r['kernels'])
        key=tuple(r['case'])
        assert key not in label or label[key]==hit
        label[key]=hit
groups={'HIT':[],'MISS':[]};table=[]
for s in perf['summary']:
    hit=label[tuple(s['case'])]; name='HIT' if hit else 'MISS'
    assert hit==(s['case'][3]%128==64)
    ratios=[b/a for a,b in zip(s['baseline_medians_us'],s['candidate_medians_us'])]
    groups[name].extend(ratios)
    table.append(dict(case=s['case'][0],N=s['case'][3],dtype=s['case'][5],TA=s['case'][6],expected=name,
        baseline_us=s['baseline_median_us'],probe_us=s['candidate_median_us'],ratio=statistics.median(ratios),
        window0_ratio=ratios[0],window1_ratio=ratios[1]))
assert len(groups['HIT'])==32 and len(groups['MISS'])==32
assert min(groups['HIT'])>5 and min(groups['MISS'])>.8 and max(groups['MISS'])<1.25
stats={k:dict(configurations=16,windows=2,min_ratio=min(x),median_ratio=statistics.median(x),max_ratio=max(x)) for k,x in groups.items()}
summary=dict(version='v12_r55',source_sha256=digest,synthetic_not_hidden=True,
    precision=dict(configurations=164,calls=492,all_pass=True,max_tolerance_ratio=max(s['max_tolerance_ratio'] for s in check)),
    calibration=stats,method='Public run_kernel entry; serial A/B/B/A, msprof task time, 12 repeats discard3 per case/window',
    new_sanitizer_run=False,known_limitations='No new sanitizer run. Existing r30 device body unchanged; historical synchronization/FFTS warnings remain.',
    status='calibrated diagnostic ready for one Judge 15-case run; not a performance submission')
(out/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n')
with (out/'CALIBRATION.csv').open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(table[0]));writer.writeheader();writer.writerows(table)
hit=stats['HIT'];miss=stats['MISS']
report=f'''# v12_r55：r54 完整入口覆盖诊断

正式主线保持 `v12_baseline_r41.asc`。r54 Judge 15/15 Pass，但Case12为115.21μs，没有证明收益；也没有证明入口未命中。

## 代码与边界

本版是诊断版，单文件 `v12_r55_probe_r54_full_gate.asc`，SHA256 `{digest}`。

r54 的 `Eligible`、新plan、dtype/transpose/pitch/family 条件逐字复制，入口位置相同；连候选工作区申请大小也保留。申请成功后才改为现有r30 kernel的单Cube plan，仍计算全部matmul、maxN和sumM，不跳过数据、不缓存答案。未命中完整条件则继续原r41路径。

没有新增设备kernel。删除诊断模块与一行dispatch后逐字节恢复r41。CPU枚举32,768组M/N/cores，128个Eligible状态全部满足压力工作区不超过原候选申请量。最小申请5,263,360字节，最大压力需求268,224字节。枚举不是设备全域测试；NPU仍只验证当前20 Cube。

## 本地验证

- Ascend910_9362、20 Cube、CANN9.0.0；完整提交代码编译通过。
- 冻结的164组合成输入×3次，共492次精度通过；含FP16/BF16、TA两值、数值压力及范围外回归。
- 参考：从实际量化输入计算CPU FP64 matmul→maxN→sumM；误差阈值`1e-4+1e-4*abs(ref)`，最大误差/阈值为{summary['precision']['max_tolerance_ratio']:.9g}。
- 32组入口校准、A/B/B/A两个窗口，每窗12次、丢弃前3次；采用msprof kernel任务时间。预期命中标签与先前实际r54 kernel名称交叉核对。
- 16组HIT全部出现明确压力：各窗口r55/r41为 **{hit['min_ratio']:.2f}～{hit['max_ratio']:.2f}倍**。
- 16组MISS：各窗口r55/r41为 **{miss['min_ratio']:.3f}～{miss['max_ratio']:.3f}倍**。
- 未新增sanitizer运行。设备代码未改，既有FFTS/同步检查限制仍保留；不能称为全域sanitizer验收。

以上合成输入不是Judge隐藏15点。原始源码、输入种子及哈希、数值日志和profiler记录在evidence.tar.gz，逐点结果见CALIBRATION.csv。

## Judge 解读与下一步

只提交这个诊断文件跑15点，回传时标注r55；不要作为冲榜基线。

1. Case12 Pass并明显进入毫秒级、远高于正常约115μs：支持完整r54入口HIT；随后检查本地计时条件与Judge收益迁移，不再归因为未启用。
2. Case12 Pass仍在约115μs且没有压力信号：支持完整入口MISS；不能单独推出N%128==0，核数、分块等也可能拒绝。继续以r41/r30原覆盖域推进B/NZ加载实验，不直接强开r53。
3. Fail或中间态：不解码，先检查版本对应和执行状态。

更可靠的压力判定是与同期基线相比至少5倍；本地绝对毫秒数不是Judge的固定预测。HIT/MISS推断要求输入、入口元数据及测评环境与r54可比。
'''
(out/'REPORT.md').write_text(report,encoding='utf-8')
readme=f'''# v12_r55：确认 r54 是否真正启用

**这是诊断版，正式主线仍是r41。只提交 `v12_r55_probe_r54_full_gate.asc` 一个文件跑完整15点。**

r54本次15/15 Pass，Case12=115.21μs，无明确收益。r55沿用r54全部入口条件，命中后单Cube完成全部真实计算，形成强耗时信号。

- Case12 Pass且明显进入毫秒级（相比同期基线至少5倍）：完整入口HIT。
- Case12 Pass仍约115μs：无压力信号，支持完整入口MISS；不能直接推出N的余数。
- Fail或信号不清晰：暂不推断。

完整CANN编译通过；164组×3次精度通过。32组合成校准中，16组HIT为{hit['min_ratio']:.2f}～{hit['max_ratio']:.2f}倍；16组MISS为{miss['min_ratio']:.3f}～{miss['max_ratio']:.3f}倍。没有新增设备kernel或sanitizer验收。回传截图请标注r55。

SHA256：`{digest}`。

[完整校准报告](../V12_npu_lab/results/r55_coverage_20261001/REPORT.md)
'''
(v/'v12_r55_README.md').write_text(readme,encoding='utf-8')
p=v/'v12_r55_manifest.json';meta=json.loads(p.read_text());meta.update(status=summary['status'],numerical_validation=summary['precision'],calibration=stats,new_sanitizer_run=False)
p.write_text(json.dumps(meta,indent=2)+'\n')
main=json.loads((v/'MAINLINE.json').read_text(encoding='utf-8'))
assert main['accepted_sota']=='v12_baseline_r41.asc'
main.update(active_diagnostic=dict(version='v12_r55',file=src.name,sha256=digest,status=summary['status'],purpose='Exact r54 full launch guard coverage',readme='v12_r55_README.md'),
    latest_diagnostic_report=meta['npu_report'],next_action='Await r55 full Judge15 coverage result, retaining r41; then choose transfer diagnosis or original-domain B/NZ experiment')
(v/'MAINLINE.json').write_text(json.dumps(main,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
with zipfile.ZipFile(v/'v12_r55_submission.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in [src,v/'v12_r55_README.md',v/'v12_r55_manifest.json']:z.write(p,p.name)
hashes={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file() and p.name!='SHA256SUMS.json'}
(out/'SHA256SUMS.json').write_text(json.dumps(hashes,indent=2)+'\n')
print(json.dumps(summary,indent=2))

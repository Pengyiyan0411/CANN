from pathlib import Path
import csv,hashlib,json,statistics,zipfile
r=Path(__file__).resolve().parents[1];o=r/'BMMS_V12';d=r/'V12_npu_lab/results/r23_20260928';e=d/'evidence'
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
with zipfile.ZipFile(d/'r23_evidence.zip') as z:
    assert z.testzip() is None
    inv=json.loads(z.read('INVENTORY_SHA256.json'))
    for name,digest in inv.items():
        assert not Path(name).is_absolute() and '..' not in Path(name).parts
        assert hashlib.sha256(z.read(name)).hexdigest()==digest,name
    z.extractall(e)
src=o/'v12_r23_probe_r22_coverage.asc';manifest=json.loads((o/'v12_r23_manifest.json').read_text(encoding='utf-8'))
assert sha(src)==manifest['sha256']==sha(e/'r23.asc')
assert sha(o/'v12_baseline_r19.asc')==manifest['parent_sha256']==sha(e/'r19.asc')
assert 'R23_SIGNAL_DONE' in (e/'results/r23_job.log').read_text()
precision={};hits=0
datasets={'screen':'cases_c1112_screen','holdout':'cases_c1112_holdout','original':'cases','c8':'cases_c8_final','split':'cases_split','controls':'cases_split_controls','gap':'cases_c12_holdout'}
def predicate(c):
    _,B,M,N,K,dt,ta,tb=c
    return B==1 and 1024<=M<2048 and 2048<=N<=8192 and 1536<=K<4096 and dt in (1,2) and M%16==0 and N%16==0 and K%32==0 and ((ta and M%64!=0) or (K if tb else N)%64!=0)
for key,folder in datasets.items():
    cases=[list(map(int,s.split())) for s in (e/f'{folder}/manifest.txt').read_text().splitlines() if s.strip()]
    results=[json.loads(s) for s in (e/f'results/r23_{key}_correctness.jsonl').read_text().splitlines()]
    assert len(results)==len(cases) and all(x['pass'] and x['repeats']==3 for x in results)
    assert [x['case'] for x in results]==[x[0] for x in cases]
    hit=sum(bool(predicate(c)) for c in cases);hits+=hit
    precision[key]=dict(cases=len(cases),executions=sum(x['repeats'] for x in results),predicted_hits=hit,all_pass=True,
        max_tolerance_ratio=max(x['max_tolerance_ratio'] for x in results))
signal=json.loads((e/'results/r23_signal_summary.json').read_text())
assert signal['source_sha256']['r23']==sha(src) and signal['source_sha256']['r19']==sha(e/'r19.asc')
cases=[x['case'] for x in signal['summary']]
block_evidence=[]
for v in ['r19','r23']:
    for w in [0,1]:
        files=list(e.glob(f'profiles/r23_signal_{v}_w{w}/PROF_*/mindstudio_profiler_output/op_summary*.csv'))
        assert len(files)==1
        rows=[x for x in csv.DictReader(files[0].open()) if 'bmms' in x.get('Op Name','')]
        rows.sort(key=lambda x:float(x['Task Start Time(us)']))
        assert len(rows)==len(cases)*20
        for i,c in enumerate(cases):
            group=rows[i*20:(i+1)*20]
            blocks=sorted({int(x['Block Num']) for x in group})
            mix=sorted({int(x['Mix Block Num']) for x in group})
            hit=bool(predicate(c))
            if v=='r23' and hit:assert blocks==[1] and mix==[2]
            else:assert min(blocks)>1
            block_evidence.append(dict(version=v,window=w,case=c[0],predicted_hit=hit,block_nums=blocks,mix_block_nums=mix))
records=[]
for x in signal['summary']:
    c=x['case'];hit=bool(predicate(c));aa=x['baseline_median_us'];bb=x['candidate_median_us']
    if hit:assert bb/aa>5,(c,aa,bb)
    records.append(dict(case=c,predicted_hit=hit,baseline_us=aa,probe_us=bb,ratio=bb/aa,
        baseline_windows_us=x['baseline_medians_us'],probe_windows_us=x['candidate_medians_us']))
host=json.loads((r/'V12_npu_lab/host_r23/RESULTS.json').read_text());assert host['passed'] and host['source_sha256']==sha(src)
summary=dict(kind='coverage diagnostic, not optimization',source_sha256=sha(src),parent_sha256=sha(e/'r19.asc'),host=host,
    precision=precision,total_cases=sum(x['cases'] for x in precision.values()),total_executions=sum(x['executions'] for x in precision.values()),
    predicted_hit_cases=hits,signal=records,profile_block_evidence=block_evidence,evidence_files_verified=len(inv),
    sanitizer='No new instrumented run. Original r19/r22 race/init findings remain unresolved; no complete sanitizer pass claimed.')
dump(d/'SUMMARY.json',summary)
rows='\n'.join(f"|{x['case'][0]}|{','.join(map(str,x['case'][2:5]))}|{'TN' if x['case'][6] and not x['case'][7] else 'TT' if x['case'][6] else 'NT' if x['case'][7] else 'NN'}|{'HIT' if x['predicted_hit'] else 'NO'}|{x['baseline_us']:.3f}|{x['probe_us']:.3f}|{x['ratio']:.2f}×|" for x in records)
report=f'''# r23 完整覆盖探针验证

主线仍为 r19；r22 两次 Judge 15/15 Pass，但 11/12 没有明确收益。本轮仅交付一个诊断版本。

## 精确验证对象

r23 的 Eligible / Prefer / ValidPlan、分派位置和 workspace 申请与 r22 一致，申请失败同样返回 false。命中并分配成功后，调用原 R06 kernel，令 pM=pN=tasks=blocks=1，完整计算相同结果。非命中路径为 r19。

移除新增模块和一行 hook 后与 r19 逐字节相同；全部 device 实现不变。源码 SHA256：`{sha(src)}`。

## 本地验证

- CANN 9.0.0，Ascend910_9362，同一远端环境。完整编译通过。
- Host：{host['guard_checks']} 组条件一致性检查、{host['stress_plan_checks']} 组压力计划及 workspace 边界检查通过。
- 精度：{summary['total_cases']} 组 / {summary['total_executions']} 次调用全通过；其中 {hits} 组预测命中。覆盖 FP16/BF16、四种转置、负值等模式，以及原 Case8/Split-K/短 K 等路径。输入来自既有数据集，参考值为量化输入的 CPU FP64 计算，每输出阈值 1e-4+1e-4×abs(reference)，输出预填 NaN。
- 信号：公开 run_kernel 入口，同卡串行 A/B/B/A，20 次/窗、丢弃前 5 次，共每版本 2 窗。轻量 msprof Task Duration，不当作未插桩正式 Judge 性能。
- profiler 原始 Block Num / Mix Block Num 证实：所有预测命中校准样例均为 1 / 2；基线及未命中样例均保持多组。

|本地 ID|M,N,K|转置|预测|r19 μs|r23 μs|耗时倍数|
|---|---|---|---|---:|---:|---:|
{rows}

这些是合成校准输入，不是隐藏测试形状。以上信号只用于区分路由。

## Judge 判读与后续

仅提交 `v12_r23_probe_r22_coverage.asc`，查看完整 15 点结果。根据队友此前已校准的原 R06 单组信号，11 预计从约 101μs 上升到约 1.16ms、12 从约 124μs 上升到约 1.50ms；这是条件性参考，不是本轮实测保证。

- 明显进入同等级慢通道且 Pass：本次进入完整 r22 条件并成功申请内存。r22 未提速不能再归因于未覆盖，下一步查该输入的预排布成本、任务划分和数据复用。
- 保持正常速度且 Pass：本次未进入诊断执行；优先检查物理跨度条件，仍须保留申请失败或元数据假设不符的可能。不要继续盲调 r22 内部参数。
- 11/12 一命中一未命中：两点分开推进。
- 超时或精度失败：不可解码为 HIT/NO，先排查。

只有其他守卫和分配成功已确认，才能将 NO 进一步解释为 `(!ta || M%64==0) && ((tb?K:N)%64==0)`，不能推出 M/N/K 全都 64 对齐。

本轮未新增 sanitizer 插桩；沿用原 device 实现不等于完成安全证明，历史 race/init 未闭环仍保留。证据 zip 的 CRC 和 {len(inv)} 个文件 SHA256 已核验；原始日志、JSONL、op_summary CSV 和源码保存在 evidence 下。
'''
(d/'REPORT.md').write_text(report,encoding='utf-8')
selected=[x for x in records if x['predicted_hit']]
readme=f'''# v12_r23：r22 覆盖探针

**这是诊断版，命中时故意单组计算、速度会明显变慢；主线仍为 r19。**

r22 两次结果：11=100.70 / 102.12μs，12=124.21 / 124.40μs，无明确收益。一次 r23 同时判断 11/12 是否进入了 r22 的完整条件，避免继续在覆盖范围不明时调参。

提交 [v12_r23_probe_r22_coverage.asc](v12_r23_probe_r22_coverage.asc)，回传完整 15 点结果即可。

|结果（须 Pass）|结论|
|---|---|
|11 从约 101μs 升至原单组毫秒通道，或 12 从约 124μs 升至该通道|对应点进入完整条件且分配成功；查命中后为何 NZ 无收益|
|仍在正常耗时附近|本次没有进入；优先核对跨度守卫，保留分配失败/元数据假设错误的可能|
|超时或精度失败|不能判读|

同型号 NPU 编译通过，{summary['total_cases']} 组 / {summary['total_executions']} 次数值通过。5 个命中校准输入耗时增加 {min(x['ratio'] for x in selected):.1f}～{max(x['ratio'] for x in selected):.1f} 倍；profiler 确认为单组。3 个未命中样例保持多组。合成校准不是隐藏输入结论。

[验证报告与局限](../V12_npu_lab/results/r23_20260928/REPORT.md) · [r22 反馈](../V12_results/2026-09-28_r22_feedback/ANALYSIS.md)。
'''
(o/'v12_r23_README.md').write_text(readme,encoding='utf-8')
manifest.update(status='CANN build, host invariants, 348-case precision and calibrated full-entry signal passed; Judge pending',
    total_precision_cases=summary['total_cases'],total_precision_calls=summary['total_executions'],report='../V12_npu_lab/results/r23_20260928/REPORT.md')
dump(o/'v12_r23_manifest.json',manifest)
main=json.loads((o/'MAINLINE.json').read_text(encoding='utf-8'));assert main['accepted_version']=='v12_r19'
old=main.get('active_diagnostic')
if old and old['version']!='v12_r23':
    main.setdefault('historical_diagnostics',[])
    if not any(x['version']==old['version'] for x in main['historical_diagnostics']):main['historical_diagnostics'].append(old)
main.update(active_diagnostic=dict(version='v12_r23',file=src.name,sha256=sha(src),parent='v12_baseline_r19.asc',
    purpose='exact r22 guards and allocation then original R06 single-group computation',status='locally validated; Judge pending',readme='v12_r23_README.md',historical=False),
    recommended_candidate=None,next_action='Run r23 once on all15; decode 11/12 coverage before further NZ tuning; r19 remains accepted')
dump(o/'MAINLINE.json',main)
p=o/'README.md';lines=p.read_text(encoding='utf-8').splitlines();lines[2]='**当前主线：** [r19](v12_baseline_r19.asc)。r21/r22 无明确 Judge 收益，不晋升。下一份为单个诊断版 [r23：r22 覆盖探针](v12_r23_README.md)，本地验证完成，待测评。以下为历史记录。';p.write_text('\n'.join(lines)+'\n',encoding='utf-8')
with zipfile.ZipFile(o/'v12_r23_submission.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in [src,o/'v12_r23_README.md',o/'v12_r23_manifest.json']:z.write(p,p.name)
print(json.dumps({k:summary[k] for k in ['total_cases','total_executions','predicted_hit_cases','evidence_files_verified']},ensure_ascii=False))
print(json.dumps(records,ensure_ascii=False,indent=2))

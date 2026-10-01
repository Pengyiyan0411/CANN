from pathlib import Path
import csv,hashlib,json,statistics,zipfile
r=Path(__file__).resolve().parents[1];o=r/'BMMS_V12';d=r/'V12_npu_lab/results/r24_20260928';e=d/'evidence'
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
with zipfile.ZipFile(d/'r24_evidence.zip') as z:
    assert z.testzip() is None
    inv=json.loads(z.read('INVENTORY_SHA256.json'))
    for name,digest in inv.items():
        assert not Path(name).is_absolute() and '..' not in Path(name).parts
        assert hashlib.sha256(z.read(name)).hexdigest()==digest,name
    z.extractall(e)
src=o/'v12_r24_probe_r22_complement.asc';manifest=json.loads((o/'v12_r24_manifest.json').read_text(encoding='utf-8'))
assert sha(src)==manifest['sha256']==sha(e/'r24.asc')
assert sha(o/'v12_baseline_r19.asc')==manifest['parent_sha256']==sha(e/'r19.asc')
assert 'R24_SIGNAL_DONE' in (e/'results/r24_job.log').read_text()
precision={};hits=0
datasets={'screen':'cases_c1112_screen','holdout':'cases_c1112_holdout','original':'cases','c8':'cases_c8_final','split':'cases_split','controls':'cases_split_controls','gap':'cases_c12_holdout'}
def predicate(c):
    _,B,M,N,K,dt,ta,tb=c
    return B==1 and 1024<=M<2048 and 2048<=N<=8192 and 1536<=K<4096 and dt in (1,2) and M%16==0 and N%16==0 and K%32==0 and not ((ta and M%64!=0) or (K if tb else N)%64!=0)
for key,folder in datasets.items():
    cases=[list(map(int,s.split())) for s in (e/f'{folder}/manifest.txt').read_text().splitlines() if s.strip()]
    results=[json.loads(s) for s in (e/f'results/r24_{key}_correctness.jsonl').read_text().splitlines()]
    assert len(results)==len(cases) and all(x['pass'] and x['repeats']==3 for x in results)
    assert [x['case'] for x in results]==[x[0] for x in cases]
    hit=sum(bool(predicate(c)) for c in cases);hits+=hit
    precision[key]=dict(cases=len(cases),executions=sum(x['repeats'] for x in results),predicted_hits=hit,all_pass=True,
        max_tolerance_ratio=max(x['max_tolerance_ratio'] for x in results))
signal=json.loads((e/'results/r24_signal_summary.json').read_text())
assert signal['source_sha256']['r24']==sha(src) and signal['source_sha256']['r19']==sha(e/'r19.asc')
cases=[x['case'] for x in signal['summary']]
block_evidence=[]
for v in ['r19','r24']:
    for w in [0,1]:
        files=list(e.glob(f'profiles/r24_signal_{v}_w{w}/PROF_*/mindstudio_profiler_output/op_summary*.csv'))
        assert len(files)==1
        rows=[x for x in csv.DictReader(files[0].open()) if 'bmms' in x.get('Op Name','')]
        rows.sort(key=lambda x:float(x['Task Start Time(us)']))
        assert len(rows)==len(cases)*20
        for i,c in enumerate(cases):
            group=rows[i*20:(i+1)*20]
            blocks=sorted({int(x['Block Num']) for x in group})
            mix=sorted({int(x['Mix Block Num']) for x in group})
            hit=bool(predicate(c))
            if v=='r24' and hit:assert blocks==[1] and mix==[2]
            else:assert min(blocks)>1
            block_evidence.append(dict(version=v,window=w,case=c[0],predicted_hit=hit,block_nums=blocks,mix_block_nums=mix))
records=[]
for x in signal['summary']:
    c=x['case'];hit=bool(predicate(c));aa=x['baseline_median_us'];bb=x['candidate_median_us']
    if hit:assert bb/aa>5,(c,aa,bb)
    records.append(dict(case=c,predicted_hit=hit,baseline_us=aa,probe_us=bb,ratio=bb/aa,
        baseline_windows_us=x['baseline_medians_us'],probe_windows_us=x['candidate_medians_us']))
host=json.loads((r/'V12_npu_lab/host_r24/RESULTS.json').read_text());assert host['passed'] and host['source_sha256']==sha(src)
summary=dict(kind='coverage diagnostic, not optimization',source_sha256=sha(src),parent_sha256=sha(e/'r19.asc'),host=host,
    precision=precision,total_cases=sum(x['cases'] for x in precision.values()),total_executions=sum(x['executions'] for x in precision.values()),
    predicted_hit_cases=hits,signal=records,profile_block_evidence=block_evidence,evidence_files_verified=len(inv),
    sanitizer='No new instrumented run. Original r19/r22 race/init findings remain unresolved; no complete sanitizer pass claimed.')
dump(d/'SUMMARY.json',summary)

selected=[x for x in records if x['predicted_hit']]
fallback=[x for x in records if not x['predicted_hit']]
assert len(selected)==7 and len(fallback)==5
rows='\n'.join(f"|{x['case'][0]}|{','.join(map(str,x['case'][2:5]))}|{x['case'][5]}|{x['case'][6]},{x['case'][7]}|{'HIT' if x['predicted_hit'] else 'NO'}|{x['baseline_us']:.3f}|{x['probe_us']:.3f}|{x['ratio']:.2f}×|" for x in records)
report=f'''# r24：r22 物理跨度守卫互补诊断

r23 Judge 全 15 点 Pass；Case11=101.79μs、Case12=123.57μs，均未出现预先校准的强压力信号。按对话唯一前序候选归属 r23，截图无源码哈希。主线仍为 r19。

## 本轮只改变哪一项

- r23：Eligible && Prefer && ValidPlan && 同大小 workspace 分配成功。
- r24：Eligible && **!Prefer** && ValidPlan && 同大小 workspace 分配成功。
- Prefer 原表达式保持不变：`(ta && M%64!=0) || ((tb ? K : N)%64!=0)`。
- 命中后仍调用原 R06 单组完整计算，pM=pN=tasks=blocks=1；没有 sleep、重复空转或答案缓存。非命中路径回到 r19。
- device 实现没有修改；去掉新增模块和一行入口后，逐字节恢复 r19。

不是优化候选，不并入主线；只获取尚缺少的正面覆盖证据。不直接放开 r22：此前不加门槛的 NZ 合成初筛中位反而变慢，最差退化 29.99%。

## 验证

源码 SHA256：`{sha(src)}`。

CANN 9.0.0 / Ascend910_9362 完整编译通过。{host['guard_checks']} 组主机检查通过，证明守卫函数文本相同且调用条件只反转 Prefer；{host['stress_plan_checks']} 组单组压力计划覆盖和 workspace 边界检查通过。

同一既有数值协议：{summary['total_cases']} 组、{summary['total_executions']} 次调用全部通过，其中 {hits} 组预测进入互补条件。覆盖 FP16/BF16、四种转置、原 Case8 / Split-K / 短 K 等输入族。参考值为实际量化输入的 CPU FP64 结果，逐输出误差阈值 1e-4+1e-4×abs(reference)，每次输出先填 NaN。此批输入不是隐藏测试形状。

公开 run_kernel 入口，串行 A/B/B/A；每窗 20 次、丢弃前 5 次，每版本 2 窗；msprof Task Duration 用于压力信号校准，不当作 Judge 性能预测。7 个命中配置耗时增至 {min(x['ratio'] for x in selected):.2f}～{max(x['ratio'] for x in selected):.2f} 倍。原始 profiler Block Num / Mix Block Num 确认命中为 1 / 2，5 个未命中配置及 r19 均为多组。

|本地 ID|M,N,K|dtype 1=FP16,2=BF16|ta,tb|预测|r19 μs|r24 μs|倍数|
|---|---|---|---|---|---:|---:|---:|
{rows}

## 只需一次 Judge

提交 `v12_r24_probe_r22_complement.asc`，查看完整 15 点结果；11/12 分开判读。

|结果，须 Pass|结论与后续|
|---|---|
|从正常约 101 / 124μs 进入明显毫秒压力通道|本次满足范围、计划及分配条件，且 Prefer=false。确认该物理跨度守卫排除了输入，暂停非对齐 NZ 路线；针对对齐跨度的原 R06 研究宏块、搬运复用、任务划分。|
|保持正常耗时附近|互补条件本次也未进入；不能声称该输入跨度对齐。复核提交源码及范围、前序路由、资源分配假设。|
|超时/精度失败|不可当作 HIT/NO，先排查。|

历史队友已校准单组压力约为 Case11 1.16ms、Case12 1.50ms，可作量级参照；并非承诺本次固定数值。不要将普通微秒波动解码为命中。

## 命中后的精确约束

Prefer=false 的等价式：`(!ta || M%64==0) && ((tb ? K : N)%64==0)`。

|布局|能推出的 64 对齐约束|
|---|---|
|NN|N；不能据此额外限制 M/K|
|NT|K；不能据此额外限制 M/N|
|TN|M、N；不能据此额外限制 K|
|TT|M、K；不能据此额外限制 N|

这些约束指所选物理 leading dimension 的 128B 跨度（FP16/BF16 每元素 2B），不是所有维度对齐，也不是内存起始地址结论。

本轮复用原设备代码，未新增 sanitizer 插桩；历史 race/init 未闭环仍保留，不声称完整 sanitizer 通过。证据 ZIP 的 CRC 和 {len(inv)} 个文件 SHA256 已核验。
'''
(d/'REPORT.md').write_text(report,encoding='utf-8')
readme=f'''# v12_r24：r22 互补覆盖探针

**诊断版，命中后故意单组计算；主线继续保留 r19。**

r23 中 11=101.79μs、12=123.57μs，均无压力信号。r24 仅反转 r22 的物理跨度筛选，其他守卫及分配条件保留，以获得正证据。

提交 [v12_r24_probe_r22_complement.asc](v12_r24_probe_r22_complement.asc)，回传完整 15 点结果。11/12 分开判读：

- 明显进入毫秒通道且 Pass：确认本次 Prefer=false，r22 的跨度门槛排除了该输入。转向对齐跨度的原 R06 优化。
- 仍为正常耗时且 Pass：暂不能判定对齐，需要复核其余条件或源码归属。
- 超时或精度失败：不可解码。

同型号 NPU 编译通过，{summary['total_cases']} 组 / {summary['total_executions']} 次数值通过；7 个命中校准样例耗时增至 {min(x['ratio'] for x in selected):.1f}～{max(x['ratio'] for x in selected):.1f} 倍，profiler 确认为单组，5 个未命中配置保持多组。

[详细验证、布局约束和检测局限](../V12_npu_lab/results/r24_20260928/REPORT.md) · [r23 结果归档](../V12_results/2026-09-28_r23_feedback/ANALYSIS.md)
'''
(o/'v12_r24_README.md').write_text(readme,encoding='utf-8')
manifest.update(status='CANN build, host invariants, precision and complementary signal calibrated; Judge pending',
    total_precision_cases=summary['total_cases'],total_precision_calls=summary['total_executions'],
    report='../V12_npu_lab/results/r24_20260928/REPORT.md')
dump(o/'v12_r24_manifest.json',manifest)
main=json.loads((o/'MAINLINE.json').read_text(encoding='utf-8'));assert main['accepted_version']=='v12_r19'
old=main.get('active_diagnostic')
if old and old['version']!='v12_r24':
    old['historical']=True
    main.setdefault('historical_diagnostics',[])
    if not any(x['version']==old['version'] for x in main['historical_diagnostics']):main['historical_diagnostics'].append(old)
main.update(active_diagnostic=dict(version='v12_r24',file=src.name,sha256=sha(src),parent='v12_baseline_r19.asc',
    purpose='r22 complement: identical Eligible/ValidPlan/allocation, inverted Prefer, original single-group R06',
    status='locally validated; Judge pending',readme='v12_r24_README.md',historical=False),
    recommended_candidate=None,next_action='Run r24 once on all15; positive stress confirms aligned physical pitches for each hit. Preserve r19.')
dump(o/'MAINLINE.json',main)
p=o/'README.md';lines=p.read_text(encoding='utf-8').splitlines();lines[2]='**当前主线：** [r19](v12_baseline_r19.asc)。r23 中 11/12 均无压力信号；下一份为 [r24：互补覆盖探针](v12_r24_README.md)，本地验证完成，待测评。r21/r22 不晋升。以下为历史记录。';p.write_text('\n'.join(lines)+'\n',encoding='utf-8')
with zipfile.ZipFile(o/'v12_r24_submission.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in [src,o/'v12_r24_README.md',o/'v12_r24_manifest.json']:z.write(p,p.name)
print(json.dumps({k:summary[k] for k in ['total_cases','total_executions','predicted_hit_cases','evidence_files_verified']},ensure_ascii=False))
print(json.dumps(records,ensure_ascii=False,indent=2))

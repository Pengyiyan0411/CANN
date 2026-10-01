from pathlib import Path
import json,hashlib,zipfile,statistics,csv,shutil
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V12';out=root/'V12_npu_lab/results/wide_pingpong_20260929'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
with zipfile.ZipFile(out/'r42_r44_evidence.zip') as z:
    assert z.testzip() is None
    manifest=json.loads(z.read('manifest.json'));hashes=manifest['files']
    assert all(hashlib.sha256(z.read(p)).hexdigest()==h for p,h in hashes.items())
    assert all(not Path(p).is_absolute() and '..' not in Path(p).parts for p in z.namelist())
    z.extractall(out/'evidence')
e=out/'evidence';validation=read(e/'results/r42_r44_validation_summary.json')
names={'r42':'v12_r42_wide_halfm_pingpong.asc','r43':'v12_r43_case8_nz_prefetch.asc','r44':'v12_r44_probe_case12_flat_gate.asc'}
assert (v/'v12_baseline_r41.asc').read_bytes()==(e/'r41.asc').read_bytes()
assert sha(v/'v12_baseline_r41.asc')=='1caf7870ac4154c0f555621ba9c41f4601c6ecee96cb2e8d0bf23acc4fc4f373'
for ver,num in [('r42',230),('r43',314),('r44',230)]:
    assert validation[ver]['precision_configurations']==num and validation[ver]['precision_calls']==num*3 and validation[ver]['all_pass']
    assert (v/names[ver]).read_bytes()==(e/f'{ver}.asc').read_bytes()
performance={}
for ver in ['r42','r43']:
    d=read(e/f'results/{ver}_screen_summary.json');rows=[]
    assert d['source_sha256'][ver]==sha(v/names[ver])
    for r in d['summary']:
        kernels=sorted({k for x in d['runs'] if x['version']==ver and x['case']==r['case'] for k in x['kernels']})
        assert all('bmms12'+ver[1:]+'_' in k for k in kernels)
        rows.append(dict(case=r['case'],baseline_us=r['baseline_median_us'],candidate_us=r['candidate_median_us'],reduction_percent=100*(1-r['candidate_median_us']/r['baseline_median_us']),window_reductions=[100*(1-b/a) for a,b in zip(r['baseline_medians_us'],r['candidate_medians_us'])]))
    vals=[r['reduction_percent'] for r in rows]
    performance[ver]=dict(count=len(rows),median_reduction_percent=statistics.median(vals),minimum=min(vals),maximum=max(vals),improved=sum(x>0 for x in vals),both_windows_improved=sum(min(r['window_reductions'])>0 for r in rows),rows=rows)
assert performance['r42']['improved']==0 and performance['r43']['improved']==0
checks={r['case']:r for tag in ['correctness','extra_correctness','holdout_correctness'] for r in map(json.loads,(e/f'results/r44_{tag}.jsonl').read_text().splitlines())}
d=read(e/'results/r44_calibration_summary.json');cal=[]
for r in d['summary']:
    ratios=[b/a for a,b in zip(r['baseline_medians_us'],r['candidate_medians_us'])]
    hit=checks[r['case'][0]]['r44_hit']
    cal.append(dict(case=r['case'],hit=hit,baseline_us=r['baseline_median_us'],probe_us=r['candidate_median_us'],ratio=r['candidate_median_us']/r['baseline_median_us'],window_ratios=ratios))
hit=[r for r in cal if r['hit']];miss=[r for r in cal if not r['hit']]
assert hit and miss and all(min(r['window_ratios'])>5 for r in hit)
assert all(max(r['window_ratios'])<1.5 for r in miss)
# Check hardware block counts for every profiled HIT, not just host plan metadata.
hw=[]
cases=[list(map(int,x.split())) for x in (e/'cases/r44_calibration.txt').read_text().splitlines()]
for path in e.glob('profiles/r44_calibration_r44_w*/PROF_*/mindstudio_profiler_output/op_summary*.csv'):
    rows=[r for r in csv.DictReader(path.open()) if 'bmms' in r.get('Op Name','')];rows.sort(key=lambda r:float(r['Task Start Time(us)']))
    assert len(rows)==len(cases)*30
    for i,c in enumerate(cases):
        if checks[c[0]]['r44_hit']:
            group=rows[i*30:(i+1)*30];assert all(int(float(r['Block Num']))==1 and int(float(r['Mix Block Num']))==2 and 'bmms1230_' in r['Op Name'] for r in group)
            hw.append(dict(case=c[0],calls=len(group),Cube=1,AIV=2))
calibration=dict(hit_count=len(hit),miss_count=len(miss),hit_range=[min(r['ratio'] for r in hit),max(r['ratio'] for r in hit)],miss_range=[min(r['ratio'] for r in miss),max(r['ratio'] for r in miss)],all_hit_hardware_counts_verified=True,rows=cal)
summary=dict(accepted_baseline='v12_baseline_r41.asc',accepted_source_sha256=sha(v/'v12_baseline_r41.asc'),performance_candidates_recommended=[],active_diagnostic=names['r44'],synthetic_not_hidden=True,validation=validation,performance=performance,calibration=calibration,evidence_files_verified=len(hashes),sanitizer='No new sanitizer run: r42/r43 rejected at screening; r44 adds host routing only and reuses existing r30 device kernel. Historical limitations remain open.')
write(out/'SUMMARY.json',summary)
table='\n'.join(f"|{ver}|{r['case'][0]}|{'×'.join(map(str,r['case'][2:5]))}|{r['case'][5]} / {r['case'][6]},{r['case'][7]}|{r['baseline_us']:.3f}|{r['candidate_us']:.3f}|{r['reduction_percent']:.2f}%|" for ver in performance for r in performance[ver]['rows'])
(out/'PERFORMANCE.md').write_text('# r42/r43全部筛选结果\n\n正降幅表示更快；构造样本ID不是比赛Case编号。两个独立进程窗口，AB/BA，各30次舍弃前5次。\n\n|版本|ID|M×N×K|dtype / ta,tb|r41 μs|实验 μs|耗时下降|\n|---|---:|---|---|---:|---:|---:|\n'+table+'\n',encoding='utf-8')
probe_table='\n'.join(f"|{r['case'][0]}|{'HIT' if r['hit'] else 'MISS'}|{r['baseline_us']:.3f}|{r['probe_us']:.3f}|{r['ratio']:.3f}×|" for r in cal)
(out/'CALIBRATION.md').write_text('# r44完整校准\n\n命中样本均由实际profiler确认1 Cube + 2 AIV，未用host wall time冒充kernel time。\n\n|ID|条件|r41 μs|r44 μs|倍数|\n|---|---|---:|---:|---:|\n'+probe_table+'\n',encoding='utf-8')
hlo,hhi=calibration['hit_range'];mlo,mhi=calibration['miss_range'];p42=performance['r42'];p43=performance['r43']
report=f'''# r41晋升、r42/r43筛选和r44最小诊断

## 当前结论

**主线已更新为v12_baseline_r41.asc。没有新的性能候选需要提交；下一份是r44诊断文件。** r41 Judge全15点Pass，Case11从r33的95.64降到83.65μs（下降12.54%），相对最近97.35μs下降14.07%。Case12为115.04μs，接近最近114.93μs，没有明确收益。版本按对r41交付的直接回复归属，截图不显示源码版本或哈希。

|隐藏点|r33旧主线 μs|r41反馈 μs|榜单参考 μs|
|---|---:|---:|---:|
|11|95.64|83.65|74.82|
|12|113.08|115.04|91.20|

这里是两次独立Judge截图，不能把小差异直接归为算法收益或退化。完整15点及原图见 `V12_results/2026-09-29_r41_feedback`。

## 两轮优化筛选

1. **r42，Case12域64×256宏块、K1=384、L0C双缓冲。** 保持完整K累加和Max-N/Sum-M顺序，将工作分成更细的M块并允许累加区交替使用。静态16384配置检查通过；230配置×3次精度全Pass。32配置均变慢，中位耗时增加{-p42['median_reduction_percent']:.2f}%，范围{-p42['maximum']:.2f}%～{-p42['minimum']:.2f}%。淘汰。更细分块增加B重复搬运和宏块数量，是可能的代价；本轮没有采集流水细项，不能把退化全部归因于某一个因素。
2. **r43，Case8 NZ跨宏块首段预取。** 只迁移r30的L1预取状态，PackInputs、host计划、微块MMAD和MaskedRowMaxConsumer保持不变。314配置×3次精度全Pass，其中84新配置包含16个初筛形状×2dtype、16个预留形状×2dtype、8个特殊值配置和12个边界/回退配置。初筛32配置均变慢，中位增加{-p43['median_reduction_percent']:.2f}%，范围{-p43['maximum']:.2f}%～{-p43['minimum']:.2f}%。淘汰，没有因为改动在别的路径有效就推定NZ路径也会有效。

|版本|同机标杆|初筛配置|精度调用|耗时下降中位数|决策|
|---|---|---:|---:|---:|---|
|r42|r41公共入口|32|690|{p42['median_reduction_percent']:.2f}%|不合入、不推荐提交|
|r43|r41公共入口|32|942|{p43['median_reduction_percent']:.2f}%|不合入、不推荐提交|

这些是构造样本，不是隐藏Case；不同shape不能拿Judge右列作为同形状标杆。原始全部数据见PERFORMANCE.md。每版两个独立进程，按AB/BA顺序，每配置30次舍弃前5次；一调用一kernel，并从实际kernel名确认新路径启用。均先通过实际量化FP16/BF16输入的CPU FP64参考，容差1e-4+1e-4×abs(ref)，每次输出先写NaN。

r43已生成并完成数值验证的预留32配置没有继续测性能；两个方案既已在初筛失败，没有扩大耗卡做晋升验证，也没有运行finish_r43.sh或新sanitizer。保留源码作为实验记录，不生成性能提交包。

## 为什么下一步只用一个探针

Case12无收益不能区分“没有命中r41”与“命中但没有加速”。r44只问这个问题，不继续二分M/N/K。其谓词为：Case12已知宽N区间，加上r41原样的dtype、Eligible、AlignedPitch和Family条件。Eligible中包含 `ceil(mTiles*nTiles/cores) < ExistingPeak(old).tiles`。

- HIT：满足条件后，用现有r30设备内核的一组Cube/AIV算完整结果；没有跳过算术、复用旧输出或改动输入。
- MISS：直接进入r41原公共入口路径。Case11与Case12区间不相交，故Case11不会被加压。
- r44不新增设备入口，仍312个。删除新增host模块和入口后可逐字节恢复r41。

完整编译通过，230配置×3次精度全Pass。公开入口26配置校准：{len(hit)}个HIT、{len(miss)}个MISS。HIT为正常耗时的{hlo:.2f}～{hhi:.2f}倍，MISS为{mlo:.3f}～{mhi:.3f}倍；全部HIT的实际Block Num=1、Mix Block Num=2。详细数据见CALIBRATION.md。

**提交r44后看Case12：显著超过正常耗时约5倍且Pass，读为HIT；仍在约115μs附近且Pass，读为MISS；Fail或中间态不作推断。** 校准倍数来自构造样本，不承诺隐藏点的绝对毫秒值。

MISS说明r41未选择展平路径，应集中分析原r30在宽N、相同峰值宏块数下的搬运与面板复用；HIT则说明不能靠放宽门槛解决，应分析已启用展平路径的尾部工作量和流水。两者都继续保留128×256宏块作为对照，不沿r42的细M分块盲调。B面板驻留可以列为下一假说，但需检查K长度下L1预算、四种layout和重复A搬运的代价，尚未实现或验证。

## 检查边界与复现

设备Ascend910_9362、20 Cube、CANN9.0.0、dav-2201。沿用独立C ABI程序，没有将项目改造成Torch扩展。r42资源预算：L1 491520B、L0A 16384B、L0B 65536B、L0C 131072B、显式UB最大54208B。r43所有pack/host/consumer字节归一化对比一致；事件逻辑模型覆盖120个任务序列、544宏块、2448个L1阶段。模型不是硬件异步竞争证明。

r44首轮构建因测试程序残留r37 planner引用失败，修复测试程序引用后重新完整构建；提交源码未因此变化，失败日志保留。r42 CPU审计首次缺algorithm头文件，补齐后重跑通过。历史r41有限memcheck超时及基线race/init问题未关闭，本轮没有声称sanitizer全通过。

证据包r42_r44_evidence.zip内{len(hashes)}文件SHA256和ZIP CRC已核验，保留源码、构建日志、种子/输入哈希/manifest、数值记录和原始profiler CSV。大输入可用生成器重建；本地生成/审计脚本也已归档。

关键结论：r41的Case11收益明确，应保留；r42/r43未通过同机筛选，不转嫁给Judge试错；Case12现阶段只需一次明确的路由门槛诊断，随后按真实路径继续分析。
'''
(out/'REPORT.md').write_text(report,encoding='utf-8')
readme=f'''# v12_r44：仅检测Case12的r41展平门槛

**诊断版，不是冲榜版。正式主线是v12_baseline_r41.asc。**

提交 `v12_r44_probe_case12_flat_gate.asc`，只需这一个探针。Case11保持r41路径。

- Case12显著变慢（约正常5倍以上）且Pass：HIT，r41此前确实满足启用条件。
- Case12仍约115μs且Pass：MISS，r41未启用，应沿原r30路径优化。
- Fail或信号不清楚：不推断。

已完整编译；230配置、690次精度调用全部通过。26个构造配置公开入口校准：{len(hit)} HIT为{hlo:.2f}～{hhi:.2f}倍，{len(miss)} MISS为{mlo:.3f}～{mhi:.3f}倍。HIT实际1 Cube+2 AIV完成真实计算，不跳过计算或复用结果。

本轮r42、r43均在本地筛选淘汰，勿作为性能版本提交。没有新增sanitizer全量验收，历史限制沿用。

[实验与校准报告](../V12_npu_lab/results/wide_pingpong_20260929/REPORT.md)

SHA256：`{sha(v/names['r44'])}`。
'''
(v/'v12_r44_README.md').write_text(readme,encoding='utf-8')
main=read(v/'MAINLINE.json');assert main['accepted_version']=='v12_r41'
for ver in ['r42','r43']:
    status=f"Rejected locally: all32screen configs slower; median regression {-performance[ver]['median_reduction_percent']:.2f}%; r41 remains accepted"
    p=v/f'v12_{ver}_manifest.json';meta=read(p);meta.update(status=status,validation=validation[ver],performance=performance[ver]|{'rows':'see experiment report'},report='../V12_npu_lab/results/wide_pingpong_20260929/REPORT.md',sanitizer_run=False);write(p,meta)
    main['candidates']=[x for x in main['candidates'] if x['version']!='v12_'+ver]
    main['candidates'].append(dict(version='v12_'+ver,file=names[ver],parent='v12_baseline_r41.asc',sha256=sha(v/names[ver]),status=status,npu_report=meta['report']))
meta=read(v/'v12_r44_manifest.json');meta.update(status='Calibrated diagnostic; Judge pending; not a performance candidate',validation=validation['r44'],calibration={k:value for k,value in calibration.items() if k!='rows'},report='../V12_npu_lab/results/wide_pingpong_20260929/REPORT.md');write(v/'v12_r44_manifest.json',meta)
main.update(recommended_candidate=None,active_diagnostic=dict(version='v12_r44',file=names['r44'],sha256=sha(v/names['r44']),parent='v12_baseline_r41.asc',purpose=meta['predicate'],status=meta['status'],readme='v12_r44_README.md'),latest_experiment_report=meta['report'],next_action='Submit only r44 diagnostic once; interpret Case12 flat-route coverage. Keep r41 accepted, reject r42/r43.')
write(v/'MAINLINE.json',main)
with zipfile.ZipFile(v/'v12_r44_submission.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in [v/names['r44'],v/'v12_r44_README.md',v/'v12_r44_manifest.json']:z.write(p,p.name)
with zipfile.ZipFile(v/'v12_r44_submission.zip') as z:assert z.testzip() is None and z.read(names['r44'])==(v/names['r44']).read_bytes()
repro=out/'local_reproduction';repro.mkdir(exist_ok=True)
for f in ['accept_r41_feedback.py','prepare_r42.py','audit_r42.py','prepare_r43.py','audit_r43.py','prepare_r44.py','release_r42_r44.py']:
    shutil.copyfile(root/'V12_npu_lab'/f,repro/f)
write(repro/'manifest.json',{p.name:sha(p) for p in repro.glob('*.py')})
print(json.dumps(dict(accepted='r41',rejected=['r42','r43'],diagnostic='r44',calibration={k:value for k,value in calibration.items() if k!='rows'},validation=validation,evidence_files=len(hashes))))

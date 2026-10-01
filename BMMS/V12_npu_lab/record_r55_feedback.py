from pathlib import Path
import json, hashlib, shutil
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V12';out=root/'V12_results/2026-10-01_r55_feedback';out.mkdir(exist_ok=True)
src=v/'v12_r55_probe_r54_full_gate.asc';sha=hashlib.sha256(src.read_bytes()).hexdigest()
assert sha=='dc6121e1d966eeef85f8b0612a983d9a8fb7ea4df4fec4933a09f3c5731e86f8'
lat=[2.34,4.86,4.98,6.40,6.45,14.61,9.22,45.37,65.94,79.35,84.56,114.51,14.65,13.07,11.23]
ref=[1.37,1.83,2.44,3.23,2.33,7.16,3.69,17.32,50.68,68.65,71.25,85.25,5.21,6.08,8.31]
shutil.copyfile(Path(r'E:\Tencent Files\3232896164\nt_qq\nt_data\Pic\2026-10\Ori\ca89df13e264385ad5d4ef3b9a44344c.png'),out/'judge.png')
data=dict(version='v12_r55',attribution='Inferred from direct reply to r55 delivery; screenshot has no source version or hash',local_source_sha256=sha,
    independent_runs=1,all_15_pass=True,rows=[dict(case=i+1,status='Pass',displayed_error_percent=0,latency_us=x,displayed_reference_us=ref[i]) for i,x in enumerate(lat)],
    result='Case12 full r54 guard MISS supported: 114.51us, no calibrated stress response',
    limitations=['Requires comparable hidden input and launch metadata to r54', 'MISS does not isolate N residue from plan/core/pitch and other conjuncts'],
    decision='Retain r41 baseline; r54 was not exercised on Case12 under these conditions; next experiment is B prepack with original r30 grid and broader original metadata coverage')
(out/'RESULTS.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
rows='\n'.join(f'|{i+1}|{x:.2f}|{ref[i]:.2f}|Pass|' for i,x in enumerate(lat))
(out/'REPORT.md').write_text('''# r55反馈：Case12的r54完整入口未命中

按对r55交付的直接回复归属，截图没有版本/源码哈希标记。15点全部Pass、显示误差0.00%。Case12为114.51μs；相比r54的115.21μs没有出现压力信号。本地完整入口探针HIT校准为16.23～17.61倍、MISS为1.000～1.014倍，因此本次支持**完整入口MISS**。推断要求隐藏输入和入口元数据与r54可比。

这排除了“r54新kernel已经执行，但此次仍约115μs”作为当前首选解释。它不单独证明N%128==0：核数与新plan整除条件等同样可能拒绝。不能把未执行的优化判定为算法本身无效，更不能直接删除全部保护条件强开。

主线保留r41。下一步在原r30的Case12覆盖域做B一次性NZ预打包，保留原128×256宏块、原plan和跨宏块预取；不依赖r54新增的N余数及新宏块整除门槛。先测包含打包和全核同步的完整kernel成本，只有本地有稳定收益才交付Judge候选。

|Case|耗时μs|右侧参考μs|状态|
|--:|--:|--:|--|
'''+rows+'\n',encoding='utf-8')
feedback='../V12_results/2026-10-01_r55_feedback/RESULTS.json'
main=json.loads((v/'MAINLINE.json').read_text(encoding='utf-8'));assert main['accepted_sota']=='v12_baseline_r41.asc'
d=main.get('active_diagnostic');assert d and d['version']=='v12_r55'
d.update(status='Judge15/15Pass; Case12 114.51us, complete r54 guard MISS supported',historical=True,feedback=feedback)
main['historical_diagnostics'].append(d);main.update(active_diagnostic=None,latest_judge_feedback=feedback,next_action='Evaluate Case12 B-only NZ pack under original r30 plan; retain r41')
for c in main['candidates']:
    if c['version']=='v12_r54':c.update(status='No Judge benefit; subsequent r55 calibrated probe supports full guard MISS on Case12; not promoted',coverage_feedback=feedback)
(v/'MAINLINE.json').write_text(json.dumps(main,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=v/'v12_r55_manifest.json';m=json.loads(p.read_text());m.update(status=d['status'],judge_feedback=feedback);p.write_text(json.dumps(m,indent=2)+'\n')
p=v/'v12_r55_README.md';s=p.read_text(encoding='utf-8');p.write_text('> Judge反馈：15/15 Pass，Case12 114.51μs，无压力信号，支持r54完整入口MISS。主线仍为r41。下文是提交前记录。\n\n'+s,encoding='utf-8')
print(json.dumps(dict(recorded=str(out),case12_us=114.51,result='full_guard_MISS',baseline='r41')))

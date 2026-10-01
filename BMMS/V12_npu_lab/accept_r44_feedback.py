from pathlib import Path
import json,hashlib,shutil,zipfile
r=Path(__file__).resolve().parents[1];v=r/'BMMS_V12';o=r/'V12_results/2026-09-29_r44_feedback';o.mkdir(exist_ok=True)
vals=[2.35,4.89,5.28,6.45,6.37,13.98,8.93,45.71,65.41,79.00,82.82,113.68,14.31,13.04,11.40]
prior=json.loads((r/'V12_results/2026-09-29_r41_feedback/RESULTS.json').read_text(encoding='utf-8'))
src=v/'v12_r44_probe_case12_flat_gate.asc';digest=hashlib.sha256(src.read_bytes()).hexdigest()
shutil.copyfile(Path(r'E:\Tencent Files\3232896164\nt_qq\nt_data\Pic\2026-09\Ori\1f245a7c4dc30c1594acd29a82e32cb7.png'),o/'judge.png')
data=dict(version='v12_r44',attribution='Inferred from direct reply to r44 delivery; screenshot has no source version/hash label',source_sha256=digest,all_15_pass=True,independent_runs=1,rows=[dict(case=i+1,status='Pass',displayed_error_percent=0,latency_us=x,r41_us=prior['latency_us'][i],platform_best_us=prior['leaderboard_best_us'][i]) for i,x in enumerate(vals)],decision='Case12 MISS:113.68us versus r41 115.04us, no stress signal; do not promote diagnostic. Case11 82.82us corroborates retained r41 gain.',inference='Together with prior r40 full-domain HIT, supports rejection by the r41 strict peak-tile improvement gate. Exact pM/pN and geometry remain unknown. Under unchanged metadata/core count, old peak tile count equals ceil(total macro tiles/cores), a count lower bound; this does not prove balanced cell/byte work.')
(o/'RESULTS.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(o/'REPORT.md').write_text('''# r44反馈：Case12未启用r41

按对r44交付的直接回复归属；15点全部Pass，显示误差0.00%。Case12为113.68μs，r41前次为115.04μs，没有经过校准的压力信号，判为MISS。Case11为82.82μs，支持保留r41收益。r44仅诊断，不合入主线。

结合r40此前确认的完整域与路由条件，在隐藏输入及核数未变的前提下，r41拒绝Case12的是严格峰值宏块数下降门槛。原计划的最重核宏块数已达到ceil(mTiles*nTiles/cores)这个计数下界；这不等于每核实际元素数、搬运量或完成时间都均衡，也不确定具体pM/pN。

下一步不再以重新分配完整128×256宏块来减少峰值数量为目标。测试B面板跨M复用，保留r41主线和Case11路径；先在同机筛选，不把逻辑搬运减少直接当性能收益。完整15点见RESULTS.json。
''',encoding='utf-8')
main=json.loads((v/'MAINLINE.json').read_text(encoding='utf-8'));assert main['accepted_version']=='v12_r41'
d=main['active_diagnostic'];assert d['version']=='v12_r44';d.update(status='Judge all15 Pass; Case12 113.68us MISS; Case11 82.82us retains r41 gain',historical=True,feedback='../V12_results/2026-09-29_r44_feedback/RESULTS.json')
main['historical_diagnostics'].append(d);main.update(active_diagnostic=None,latest_judge_feedback=d['feedback'],next_action='Evaluate Case12 B-panel reuse against accepted r41; r44 MISS excludes flat peak-count improvement.')
(v/'MAINLINE.json').write_text(json.dumps(main,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=v/'v12_r44_manifest.json';meta=json.loads(p.read_text(encoding='utf-8'));meta.update(status=d['status'],judge_feedback=d['feedback']);p.write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=v/'v12_r44_README.md';s=p.read_text(encoding='utf-8');p.write_text('> Judge更新：Case12 113.68μs，无压力信号，MISS；Case11 82.82μs。主线仍为r41。下面保留提交前说明。\n\n'+s,encoding='utf-8')
with zipfile.ZipFile(v/'v12_r44_submission.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in [src,v/'v12_r44_README.md',v/'v12_r44_manifest.json']:z.write(p,p.name)
print(json.dumps(dict(version='r44',case12='MISS',baseline='r41 retained')))

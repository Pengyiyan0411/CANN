from pathlib import Path
import hashlib,json,shutil,zipfile
r=Path(__file__).resolve().parents[1];o=r/'BMMS_V12';d=r/'V12_results/2026-09-28_r33_feedback'
d.mkdir(parents=True,exist_ok=True)
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
source=o/'v12_r33_shortk_prefetch_allpitch.asc';expected='86debd5c403af4bb436d6c042de4530faf05637cf6fd1aeaae6ed6b410d11d80'
assert sha(source)==expected
baseline=o/'v12_baseline_r33.asc'
if baseline.exists():assert baseline.read_bytes()==source.read_bytes()
else:shutil.copyfile(source,baseline)
old=json.loads((r/'V12_results/2026-09-28_r30_feedback/RESULTS.json').read_text(encoding='utf-8'))
times=[2.23,4.47,4.93,6.34,6.34,14.42,8.90,45.80,64.91,79.42,95.64,113.08,14.72,13.11,11.31]
refs=[1.22,1.58,2.13,2.92,1.89,7.07,3.68,14.88,50.68,72.39,74.82,91.20,5.14,5.40,4.05]
rows=[]
for i,(t,ref,prior) in enumerate(zip(times,refs,old['cases']),1):
 assert prior['case']==i
 b=prior['latency_us'];rows.append(dict(case=i,status='Pass',displayed_error_percent=0.0,latency_us=t,platform_best_us=ref,r30_us=b,reduction_us=b-t,reduction_pct=100*(1-t/b)))
image=Path(r'E:\Tencent Files\3232896164\nt_qq\nt_data\Pic\2026-09\Ori\c1ab9c71385d7133c056945f6a75b4f7.png')
if image.exists():shutil.copyfile(image,d/'judge_r33.png')
data=dict(version='v12_r33',version_attribution='Inferred from direct response to r33 delivery; screenshot has no version/hash label',source='user screenshot',source_sha256=expected,source_hash_visible_in_screenshot=False,independent_runs=1,all_15_pass=True,screenshot_path_supplied=str(image),screenshot_copied=image.exists(),rows=rows,decision='Accept r33 as mainline; preserve r30 fallback. Cases9/10 show expected target gains; other changes not attributed to this optimization; prior sanitizer findings remain open.')
dump(d/'RESULTS.json',data)
table='\n'.join(f"|{x['case']}|{x['r30_us']:.2f}|{x['latency_us']:.2f}|{x['reduction_pct']:.2f}%|" for x in rows)
report=f'''# r33 Judge结果归档

按紧接r33交付的对话顺序归属版本；截图本身未展示版本号或源码哈希。一次独立测试，15/15 Pass，显示误差均为0.00%。已将r33固定为新基线，r30保留回退。

|Case|上一张r30（μs）|本次r33（μs）|耗时降幅|
|---|---:|---:|---:|
{table}

Case9：70.62→64.91μs，减少5.71μs（{rows[8]['reduction_pct']:.2f}%）。Case10：84.55→79.42μs，减少5.13μs（{rows[9]['reduction_pct']:.2f}%）。与本地短K域收益方向一致，支持保留这次扩展。

本次没有任何点比上一张r30更慢；但其余路径也普遍变快，存在测评环境波动。11/12为95.64/113.08μs，8/15为45.80/11.31μs；这些点的源码路径未改动，不把其下降额外记成r33算法收益。单轮截图不证明所有输入永久不退化，也不能从耗时精确反推出隐藏形状。

原本地插桩发现的L0C竞争、初始化与寄存器/同步警告仍未闭环，Judge通过不替代这些检查。

基线：[v12_baseline_r33.asc](../../BMMS_V12/v12_baseline_r33.asc)。SHA256：`{expected}`。

[本地实验报告](../../V12_npu_lab/results/dense_next_20260928/REPORT.md)为线上反馈前的历史实验记录。
'''
(d/'RESULTS.md').write_text(report,encoding='utf-8')
main=json.loads((o/'MAINLINE.json').read_text(encoding='utf-8'));assert main['accepted_version'] in ['v12_r30','v12_r33']
assert sha(o/'v12_baseline_r30.asc')=='9ac17c7b6f793cf043ee8d150479f42a1423a73ffe5c877b2456d16396d1fa17'
status='Accepted after Judge15/15Pass: Case9 64.91us, Case10 79.42us; prior sanitizer findings remain open'
feedback='../V12_results/2026-09-28_r33_feedback/RESULTS.json'
main.update(accepted_version='v12_r33',accepted_sota=baseline.name,accepted_sha256=expected,previous_sota='v12_baseline_r30.asc',acceptance_basis='Single user Judge screenshot after r33 delivery: all15 Pass; Case9 70.62->64.91us, Case10 84.55->79.42us; no point slower than previous r30 screenshot. Other improvements treated as measurement variation, not additional algorithm gains.',naming='v12_rxx; r33 accepted after Judge feedback',recommended_candidate=None,next_action='Use frozen r33 for subsequent optimization comparisons; preserve r30 fallback and unresolved sanitizer findings.',latest_judge_feedback=feedback)
for x in main['candidates']:
 if x['version']=='v12_r33':x.update(status=status,judge_feedback=feedback)
dump(o/'MAINLINE.json',main)
p=o/'v12_r33_manifest.json';meta=json.loads(p.read_text(encoding='utf-8'));meta.update(status=status,judge_feedback=feedback);dump(p,meta)
(o/'v12_r33_README.md').write_text('''# v12_r33（当前已接受基线）

Judge 15/15 Pass：Case9 64.91μs（相对上一张r30降低8.09%），Case10 79.42μs（降低6.07%）。本次没有点比上一张r30更慢；其余点的小幅下降不归因为本次算法修改。

冻结主线为[v12_baseline_r33.asc](v12_baseline_r33.asc)，[r30](v12_baseline_r30.asc)保留回退。此前竞争/初始化等插桩问题仍未闭环。

[线上完整结果](../V12_results/2026-09-28_r33_feedback/RESULTS.md) · [此前本地实验](../V12_npu_lab/results/dense_next_20260928/REPORT.md)
''',encoding='utf-8')
p=o/'README.md';lines=p.read_text(encoding='utf-8').splitlines();lines[0]='# BMMS V12：r33 主线与 v12_rxx 历史候选';lines[2]='**当前主线：** [r33](v12_baseline_r33.asc)。Judge 15/15 Pass，Case9 64.91μs、Case10 79.42μs；11/12为95.64/113.08μs，8/15为45.80/11.31μs。r30保留回退。当前没有新的待测候选。[线上结果与判读](../V12_results/2026-09-28_r33_feedback/RESULTS.md)。以下为历史记录。';p.write_text('\n'.join(lines)+'\n',encoding='utf-8')
with zipfile.ZipFile(o/'v12_r33_submission.zip','w',zipfile.ZIP_DEFLATED) as z:
 for name in [source.name,'v12_r33_manifest.json','v12_r33_README.md']:z.write(o/name,name)
 z.write(r/'V12_npu_lab/results/dense_next_20260928/REPORT.md','VALIDATION_REPORT.md');z.write(d/'RESULTS.md','JUDGE_RESULTS.md')
with zipfile.ZipFile(o/'v12_r33_submission.zip') as z:
 assert z.testzip() is None and z.read(source.name)==source.read_bytes()
assert sha(baseline)==expected
print(json.dumps(dict(accepted='r33',case9_reduction_pct=rows[8]['reduction_pct'],case10_reduction_pct=rows[9]['reduction_pct'],no_slower_in_this_pair=all(x['reduction_us']>=0 for x in rows),baseline_sha256=expected)))

from pathlib import Path
import hashlib, json, shutil, zipfile

root = Path(__file__).resolve().parents[1]
v = root / 'BMMS_V12'
out = root / 'V12_results/2026-09-29_r41_feedback'
out.mkdir(exist_ok=True)
src = v / 'v12_r41_dense_flat_macro.asc'
sha = hashlib.sha256(src.read_bytes()).hexdigest()
assert sha == '1caf7870ac4154c0f555621ba9c41f4601c6ecee96cb2e8d0bf23acc4fc4f373'
values = [2.24,4.68,5.02,6.51,6.56,14.32,8.92,46.12,65.25,79.48,83.65,115.04,14.58,13.26,11.41]
best = [1.22,1.58,2.13,2.92,1.89,7.07,3.68,14.88,50.68,72.39,74.82,91.20,5.14,5.40,4.05]
old = [2.23,4.47,4.93,6.34,6.34,14.42,8.90,45.80,64.91,79.42,95.64,113.08,14.72,13.11,11.31]
pic = Path(r'E:\Tencent Files\3232896164\nt_qq\nt_data\Pic\2026-09\Ori\95126e8ec359ce8c55ced4cf8d90fdb5.png')
shutil.copyfile(pic,out/'judge.png')
feedback = dict(version='v12_r41',source_sha256=sha,attribution='Inferred from direct response to r41 delivery; screenshot has no version/hash label',all_pass=True,displayed_error_percent=0,latency_us=values,leaderboard_best_us=best,comparison_r33_us=old,rows=[dict(case=i+1,status='Pass',displayed_error_percent=0.0,latency_us=t,platform_best_us=best[i],r33_us=old[i]) for i,t in enumerate(values)],case11_reduction_vs_r33_percent=100*(1-values[10]/old[10]),case11_reduction_vs_recent_r39_percent=100*(1-values[10]/97.35),decision='Promote r41 based on clear Case11 gain; Case12 no demonstrated gain. Single screenshot, no paired repeat. Preserve r33 rollback.',sanitizer='Prior limited r41 memcheck timed out after two completed cases; historical race/init findings unresolved.')
(out/'RESULTS.json').write_text(json.dumps(feedback,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
lines=['# r41 Judge反馈与主线晋升','','按用户对r41交付的直接回复归属；截图没有源码版本或哈希标签。15点全Pass，显示误差0.00%。','','|Case|r33基线 μs|r41 μs|榜单参考 μs|','|---|---:|---:|---:|']
lines += [f'|{i+1}|{a:.2f}|{b:.2f}|{c:.2f}|' for i,(a,b,c) in enumerate(zip(old,values,best))]
lines += ['','Case11从r33的95.64降至83.65μs，下降12.54%；相对最近97.35μs下降14.07%。Case12为115.04μs，处于近期114.93～116.02μs附近，没有明确收益。其他点未见明显退化，但单次截图不能证明没有微小退化。','','保存为v12_baseline_r41.asc，源码逐字节不变；r33保留回退。不能仅凭Case12持平就断言它没有命中r41：也可能命中但没有显著收益。下一实验优先只覆盖Case12宽N区间，保护Case11成果。','','历史sanitizer限制没有因Judge Pass而关闭：r41有限memcheck仅完成2例，第3例超时；race/init尚未闭环。']
(out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
shutil.copyfile(src,v/'v12_baseline_r41.asc')
meta_path=v/'v12_r41_manifest.json'
meta=json.loads(meta_path.read_text(encoding='utf-8'))
meta.update(status='Accepted after Judge all15 Pass; Case11 83.65us, Case12 115.04us no clear gain; prior sanitizer limitations remain open',judge_feedback='../V12_results/2026-09-29_r41_feedback/RESULTS.json')
meta_path.write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=v/'MAINLINE.json';main=json.loads(p.read_text(encoding='utf-8'))
main.update(accepted_sota='v12_baseline_r41.asc',accepted_sha256=sha,accepted_version='v12_r41',previous_sota='v12_baseline_r33.asc',acceptance_basis=feedback['decision']+' Case11 95.64->83.65us (-12.54%); latest normal97.35->83.65us (-14.07%).',naming='v12_rxx; r41 accepted after Judge feedback',recommended_candidate=None,next_action='Investigate isolated Case12 optimization against r41; do not infer route noncoverage from unchanged timing.',latest_judge_feedback='../V12_results/2026-09-29_r41_feedback/RESULTS.json')
for c in main['candidates']:
    if c['version']=='v12_r41': c.update(status=meta['status'],judge_feedback=meta['judge_feedback'])
p.write_text(json.dumps(main,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
readme=v/'v12_r41_README.md';s=readme.read_text(encoding='utf-8')
s=s.replace('**性能候选，主线仍为r33。提交 `v12_r41_dense_flat_macro.asc`，不要提交r40压力探针。**','**现已接受为主线 `v12_baseline_r41.asc`。Judge 15点Pass；Case11 83.65μs，Case12 115.04μs无明确收益。**\n\n[最新Judge记录](../V12_results/2026-09-29_r41_feedback/REPORT.md)。下方保留提交前验证记录。')
s=s.replace('Judge待测。','此为提交前覆盖判断；最新Judge结果见上方。').replace('请回传15点结果，重点看11/12及其余点有无稳定退化。','已收到15点结果并归档，源码没有修改。')
readme.write_text(s,encoding='utf-8')
rep=root/'V12_npu_lab/results/plan_equal_20260929/REPORT.md'
s=rep.read_text(encoding='utf-8');s=s.replace('当前正式基线仍为 **r33**。推荐下一次Judge测试 `v12_r41_dense_flat_macro.asc`；r41是性能候选，不是压力探针，尚未晋升。','**最新状态：r41已在Judge反馈后晋升主线。Case11 83.65μs、Case12 115.04μs，15点Pass。** [反馈归档](../../../V12_results/2026-09-29_r41_feedback/REPORT.md)。以下是提交前实验记录，其中“待测/未晋升”描述保留历史语境。')
rep.write_text(s,encoding='utf-8')
with zipfile.ZipFile(v/'v12_r41_submission.zip','w',zipfile.ZIP_DEFLATED) as z:
    for f in (src,readme,meta_path):z.write(f,f.name)
    z.write(out/'REPORT.md','JUDGE_FEEDBACK.md')
print(json.dumps(dict(accepted=main['accepted_sota'],sha256=sha,case11_reduction_percent=feedback['case11_reduction_vs_r33_percent']),indent=2))

from pathlib import Path
import json,hashlib,shutil
H=Path(__file__).resolve().parent;ROOT=H.parents[1]
package=ROOT/'BMMS_V11_R50';manifest=json.loads((package/'MANIFEST.json').read_text(encoding='utf-8'))
assert hashlib.sha256((package/manifest['candidate']).read_bytes()).hexdigest()==manifest['sha256']
times=[[2.41,5.01,5.29,6.50,6.50,14.24,9.51,63.37,70.41,84.20,101.23,122.95,15.20,13.78,15.14],
       [2.42,5.06,5.14,6.42,6.27,14.23,9.24,62.01,69.46,83.71,100.21,122.51,14.56,13.36,15.27]]
best=[1.22,1.58,2.13,2.92,1.89,7.07,3.68,14.88,51.62,72.39,74.82,91.20,5.14,5.40,4.05]
parent=json.loads((ROOT/'V11_results/2026-09-28_r49_feedback/FEEDBACK.json').read_text(encoding='utf-8'))
images=[]
for name in ['1bc740baa9b19dff9ec29da594a97385.png','b95fd8fb8c00e4756597c43a4b7a11ca.png']:
    p=Path('E:/Tencent Files/3232896164/nt_qq/nt_data/Pic/2026-09/Ori')/name
    if p.is_file():shutil.copyfile(p,H/name)
    images.append({'origin':str(p),'copied':(H/name).is_file()})
report={'date':'2026-09-28','candidate':manifest['candidate'],'source_sha256':manifest['sha256'],
 'version_attribution':'R50 inferred from immediate submission and user positive feedback; no version label in image',
 'sample_count':2,'all_pass_each_run':True,'displayed_error_percent_all':0.0,'images':images,
 'cases':[{'case':i+1,'latency_us':[t[i] for t in times],'mean_us':sum(t[i] for t in times)/2,
           'R49_previous_us':parent['cases'][i]['latency_us'],'platform_best_us':best[i]} for i in range(15)],
 'case2_reduction_vs_R49_previous_percent':(5.92-5.035)/5.92*100,
 'case2_reduction_vs_R48_mean_percent':(5.665-5.035)/5.665*100,
 'same_round_control':False,'route_instrumented':False,'non_regression_guaranteed':False,
 'decision':'retain R50 as new development parent; freeze R43 and retain R49 rollback'}
(H/'FEEDBACK.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
rows=['# R50 两次测评反馈','',
 '两次均15/15 Pass、显示误差0.00%。版本归属按紧邻的 R50 提交和用户反馈记录，截图自身无版本标签。',
 '', '| 点 | R49上次 | R50第1次 | R50第2次 | R50均值 | 平台最优 |', '|---|---:|---:|---:|---:|---:|']
for c in report['cases']:
    rows.append(f"| {c['case']} | {c['R49_previous_us']:.2f} | {c['latency_us'][0]:.2f} | {c['latency_us'][1]:.2f} | {c['mean_us']:.3f} | {c['platform_best_us']:.2f} |")
rows+=['','单位μs。点2均值5.035，相比R49单次5.92降低14.95%，相比R48两次均值5.665降低11.12%。没有同轮交替对照，不把这些百分比当成精确因果收益。',
 '','第2次许多点整体更快，而点2两次接近；支持保留R50，但没有证明其他点的小幅变化由R50造成。点5/7/8/13/15均维持已有性能区间。',
 '','R50作为后续开发父版，R43冻结、R49回退保留。下一轮R51只扩展到多batch小矩阵。']
(H/'RESULTS.md').write_text('\n'.join(rows)+'\n',encoding='utf-8')
print(json.dumps({'case2_mean_us':5.035,'all_pass':True,'images':images},ensure_ascii=False))

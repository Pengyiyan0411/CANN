from pathlib import Path
import json,hashlib,shutil
root=Path(__file__).resolve().parents[1];out=root/'BMMS_V12'
src=out/'v12_r19_case8_nz_explicit_tail.asc';digest=hashlib.sha256(src.read_bytes()).hexdigest()
assert digest=='27ff91a8e886644ba99b68e3a59ed4d5ed0a001039d6c56074df098d4c66c021'
base=out/'v12_baseline_r19.asc';base.write_bytes(src.read_bytes())
d=root/'V12_results/2026-09-28_r19_feedback';d.mkdir(parents=True,exist_ok=True)
times=[2.34,4.74,5.25,6.38,6.42,14.93,9.58,46.88,70.04,84.62,101.76,124.47,15.58,13.96,11.29]
best=[1.22,1.58,2.13,2.92,1.89,7.07,3.68,14.88,50.68,72.39,74.82,91.20,5.14,5.40,4.05]
feedback=dict(version='v12_r19',attribution='Unique preceding candidate; user screenshot, platform source hash not exposed',source_sha256=digest,all_pass=True,cases=[dict(case=i+1,pass_=True,error_pct=0,latency_us=t,best_us=b) for i,(t,b) in enumerate(zip(times,best))])
(d/'RESULTS.json').write_text(json.dumps(feedback,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(d/'RESULTS.md').write_text('# r19 Judge反馈\n\n用户截图15/15 Pass、误差列均0.00%。按唯一前序候选归属r19，平台未展示源hash。\n\nCase8为46.88 μs，相对历史约62–63 μs缩短约24–26%；这是跨轮比较，不是相邻配对基准。Case15为11.29 μs，保留此前约11.5 μs成果。其他点本轮无明显大幅回退，但单次截图不能证明所有小差异均为噪声。\n\n冻结`v12_baseline_r19.asc`为主线，r12保留回退；本地race/init未关闭告警仍如实保留，不因Judge Pass消除。完整15点见RESULTS.json。\n',encoding='utf-8')
img=Path('E:/Tencent Files/3232896164/nt_qq/nt_data/Pic/2026-09/Ori/4de368cf54d4cd62e9a8eb949a397cfe.png')
if img.exists():shutil.copyfile(img,d/'judge.png')
m=json.loads((out/'MAINLINE.json').read_text(encoding='utf-8'))
m.update(accepted_sota=base.name,accepted_sha256=digest,accepted_version='v12_r19',previous_sota='v12_baseline_r12.asc',acceptance_basis='User screenshot 15/15 Pass; Case8 46.88us, Case15 11.29us. Single-run comparison; source attribution by conversation.',naming='v12_rxx; r19 accepted after Judge feedback',next_action='Case12 local packet-plan experiments; preserve r19 baseline',recommended_candidate=None)
for c in m['candidates']:
 if c['version']=='v12_r19':c.update(status='accepted after Judge 15/15 Pass; Case8 46.88us, Case15 11.29us; sanitizer limitations retained',judge_feedback='../V12_results/2026-09-28_r19_feedback/RESULTS.json')
(out/'MAINLINE.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
mp=out/'v12_r19_manifest.json';m=json.loads(mp.read_text(encoding='utf-8'));m.update(status='accepted after Judge feedback; race/init limitations retained',judge_feedback='../V12_results/2026-09-28_r19_feedback/RESULTS.json');mp.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
notice='> Judge已通过15/15：Case8 46.88 μs、Case15 11.29 μs；r19已冻结为主线。以下本地候选报告保留原始时间点。\n\n'
p=out/'v12_r19_README.md';t=p.read_text(encoding='utf-8')
if not t.startswith(notice):p.write_text(notice+t,encoding='utf-8')
p=out/'README.md';lines=p.read_text(encoding='utf-8').splitlines();lines[0]='# BMMS V12：r19 主线与 v12_rxx 候选';lines[2]='**当前主线：** [v12_baseline_r19.asc](v12_baseline_r19.asc)，Judge 15/15 Pass，Case8 46.88 μs、Case15 11.29 μs。下一方向为Case12，以下内容是历史记录。';p.write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('r19 frozen',digest)

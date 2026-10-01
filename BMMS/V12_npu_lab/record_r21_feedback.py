from pathlib import Path
import json,hashlib,shutil
r=Path(__file__).resolve().parents[1];d=r/'V12_results/2026-09-28_r21_feedback';d.mkdir(parents=True,exist_ok=True);o=r/'BMMS_V12'
times=[2.33,4.79,5.19,6.45,6.49,14.78,9.68,46.99,70.71,84.43,101.08,122.28,15.03,13.84,10.94]
best=[1.22,1.58,2.13,2.92,1.89,7.07,3.68,14.88,50.68,72.39,74.82,91.20,5.14,5.40,4.05]
base=json.loads((r/'V12_results/2026-09-28_r19_feedback/RESULTS.json').read_text(encoding='utf-8'))
rows=[dict(case=i+1,pass_=True,error_pct=0,latency_us=t,best_us=b,r19_us=base['cases'][i]['latency_us']) for i,(t,b) in enumerate(zip(times,best))]
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
dump(d/'RESULTS.json',dict(version='v12_r21',attribution='Unique preceding candidate; platform hash unavailable',source_sha256=hashlib.sha256((o/'v12_r21_case12_packet_tail.asc').read_bytes()).hexdigest(),all_pass=True,cases=rows,decision='not promoted: Case12 122.28us within historical range; dispatch unknown'))
img=Path('E:/Tencent Files/3232896164/nt_qq/nt_data/Pic/2026-09/Ori/24bb51950d61d4ada613c78230028870.png')
if img.exists():shutil.copyfile(img,d/'judge.png')
notes='''# r21反馈与11/12新探针

r21全15点Pass。Case12从r19截图124.47到122.28μs（单次差−1.76%），仍落在既往121～125μs范围，不能认定有稳定收益。Case8=46.99μs、Case15=10.94μs。保留r19主线，r21不晋升；仅凭耗时无法判定r21是否触发。

## 新证据（用户转述队友探针，未获得对应源码/原始截图）

两点R06_STRESS_ALL强命中；N_GE2048命中、M_GE2048不命中；Case12 K_GE1792不命中；Case11 K_GE4096不命中。结合此前约束：

| 点 | B | M | N | K |
|---|---|---|---|---|
|11|1|1024～2032，步16|2048～8192，步16|2048～4064，步32|
|12|1|1024～2032，步16|2048～8192，步16|1536～1760，步32|

K12<K11确实成立，但同一个M区间不等于M相同，同一个N区间也不等于工作量接近。还未知dtype/layout、物理行跨度、K尾片比例，以及具体任务格。不能将差距仅归结为N或planner。

原R06计划选择仅依赖B/M/N/cores，不依赖K；K影响每个宏块耗时、K1/K0尾片，以及TB布局的物理源跨度。下轮首先在新范围比较同一原计划下ND直接搬运与一次NZ预排布，隔离搬运成本。r21峰值门槛和更换布局是两条不同假设，不叠加调参。

若队友继续测：优先N_GE4096与M_GE1536；若目的仅验证r21无效原因，一次“r21计划确实Changed时执行已校准R06 stress”的覆盖探针比继续精确K更直接。单纯r21耗时无变化不能判定Changed为false。K_GE1664/3072可随后推进，不作为本地实验的前置条件。
'''
(d/'ANALYSIS.md').write_text(notes,encoding='utf-8')
m=json.loads((o/'MAINLINE.json').read_text(encoding='utf-8'));assert m['accepted_version']=='v12_r19'
for c in m['candidates']:
 if c['version']=='v12_r21':c.update(status='Judge 15/15 Pass; no clear Case12 gain; not promoted',judge_feedback='../V12_results/2026-09-28_r21_feedback/RESULTS.json')
m.update(recommended_candidate=None,next_action='Case11/12 narrowed-domain ND vs NZ experiments; keep r19 accepted');dump(o/'MAINLINE.json',m)
p=o/'v12_r21_manifest.json';m=json.loads(p.read_text(encoding='utf-8'));m.update(status='Judge all15 Pass; no clear Case12 gain; not promoted',judge_feedback='../V12_results/2026-09-28_r21_feedback/RESULTS.json');dump(p,m)
p=o/'v12_r21_README.md';t=p.read_text(encoding='utf-8');notice='> Judge反馈：Case12 122.28μs，无明确收益，r21不晋升；主线仍为r19。以下为提交前实验记录。\n\n'
if not t.startswith(notice):p.write_text(notice+t,encoding='utf-8')
p=o/'README.md';lines=p.read_text(encoding='utf-8').splitlines();lines[2]='**当前主线：** [r19](v12_baseline_r19.asc)。r21全15点Pass但Case12无明确收益，不晋升；下一步按新11/12范围检查搬运策略。以下为历史记录。';p.write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(d)

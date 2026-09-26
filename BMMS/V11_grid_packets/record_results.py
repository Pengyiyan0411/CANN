"""Retain raw, user-labelled measurements; never treat a single run as noise-free."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math
import shutil

HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
OUT=ROOT/'V11_results/2026-09-26_r05_r06_submission'
TIMES={
 'R05':[2.56,5.62,5.06,6.52,7.17,14.68,10.93,91.93,70.08,106.27,135.44,124.25,18.88,15.30,37.38],
 'R06':[2.42,5.80,5.10,6.64,7.77,15.36,11.24,93.65,71.53,108.43,136.39,124.78,19.47,15.64,37.63]}
T=[1.22,1.58,2.16,2.92,1.95,7.23,3.70,17.32,51.77,72.47,74.82,91.20,5.21,7.10,9.04]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,s):p.write_text(s,encoding='utf-8',newline='\n')
def scores(v):return [100/(1+math.log(a/b)/math.log(1.5)) for a,b in zip(v,T)]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--r05',type=Path);ap.add_argument('--r06',type=Path);a=ap.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    prior=json.loads((ROOT/'V11_results/2026-09-26_r04_submission/RESULT.json').read_text(encoding='utf-8'))
    manifest=json.loads((ROOT/'BMMS_V11_R05_R06/MANIFEST.json').read_text(encoding='utf-8'))
    evidence={}
    for row in manifest['variants']:
        name=row['version'];source=ROOT/'BMMS_V11_R05_R06'/row['file'];assert sha(source)==row['sha256']
        image=OUT/(name+'_user_screenshot.png');supplied=getattr(a,name.lower())
        if not image.exists():
            if supplied is None:ap.error('Screenshots required on first import')
            shutil.copyfile(supplied,image)
        elif supplied is not None:assert sha(image)==sha(supplied)
        evidence[name]={'explicit_user_label':True,'local_source_sha256':sha(source),'screenshot_sha256':sha(image),
            'platform_source_digest_available':False,'pass_count':15,'case_count':15,'times_us':TIMES[name]}
    all_times={'R04_contextual':prior['times_us'],**TIMES}
    result={'evidence':evidence,'T_us':T,'T5_previous':2.36,'T5_current':1.95,'single_observation_per_version':True,
        'noise_removed':False,'statistically_proven_speedup':False,'retained_baseline':'R04',
        'scores_same_current_T':{name:sum(scores(values))/15 for name,values in all_times.items()},
        'rows':[{'case':i+1,'R04_us':prior['times_us'][i],'R05_us':TIMES['R05'][i],'R06_us':TIMES['R06'][i],
                 'T_us':T[i],'R05_delta_pct':100*(TIMES['R05'][i]/prior['times_us'][i]-1),
                 'R06_delta_pct':100*(TIMES['R06'][i]/prior['times_us'][i]-1)} for i in range(15)]}
    write(OUT/'RESULT.json',json.dumps(result,indent=2)+'\n')
    with (OUT/'measurements.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(result['rows'][0]));w.writeheader();w.writerows(result['rows'])
    table='\n'.join(f'| {r["case"]} | {r["R04_us"]:.2f} | {r["R05_us"]:.2f} | {r["R06_us"]:.2f} | {r["T_us"]:.2f} | {r["R05_delta_pct"]:+.2f}% | {r["R06_delta_pct"]:+.2f}% |' for r in result['rows'])
    score_table='\n'.join(f'| {name} | {score:.6f} |' for name,score in result['scores_same_current_T'].items())
    write(OUT/'AUDIT.md',f'''# R05 / R06：通过，但未证明稳定提速

用户明确标注图1为R05、图2为R06，两版15/15 Pass，并提醒存在测评波动。
截图、逐点原始耗时及本地源码SHA保留；平台没有提供源码hash。0.00%为舍入显示。

| 版本 | 按本轮T复算分数 |
|---|---:|
{score_table}

点5的T从2.36降到1.95μs，故R04由上一口径34.496451变为34.299997。
不能把排行榜基准变化混作代码变慢，也不能直接沿用旧总分比较。

| 点 | R04 μs | R05 μs | R06 μs | 本轮T μs | R05对R04耗时变化 | R06对R04耗时变化 |
|---|---:|---:|---:|---:|---:|---:|
{table}

R05点9–12变化为−0.17%、−2.00%、+0.11%、+0.57%；R06为+1.89%、−0.01%、+0.81%、+1.00%。
结合用户提供的波动信息，这不足以认定两项优化有稳定收益；也不足以宣称某个流水阶段
已经被严格证明是瓶颈。R05单次总分最高，仅记录为观测值，不升级为确定更快的基线。
小点路由未公开，不能把某些点直接当作未修改路径的严格噪声对照。

## 排除波动的方法与限制

每版本仅一次观测，无法事后完全分离测量噪声与代码效应；不能用全点统一缩放“修正”数据，
也不取不同提交的逐点最小值拼总分。当前保留R04，R05/R06暂不合并。

后续建议R04→R07→R04，再R08→R04。使用同一冻结R04，比较候选与相邻两次控制的逐点
原始耗时；最新T只用于统一复算分数。改善落在两次R04耗时区间内时记为未分辨。
只有一致超出控制波动范围的收益才值得保留；这仍不是置信区间或统计显著性证明，
结果贴近边界时再重复相应候选，不立即叠加改动。

下一轮R07检查精确循环分配下的核间负载，R08将小K输出按四个微块成包，减少跨核握手。
两版分别从R04派生，不包含R05/R06。继续无NPU环境的离线检查与平台提交。
''')
    print(json.dumps(result['scores_same_current_T'],indent=2))

if __name__=='__main__':main()

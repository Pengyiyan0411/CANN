"""Retain the user-confirmed R07 case-5 runtime TLE and the R08 screenshot."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math
import shutil

HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
OUT=ROOT/'V11_results/2026-09-26_r07_r08_submission'
R08=[2.65,5.39,5.36,6.44,7.15,14.48,10.74,91.57,70.95,106.62,134.38,123.61,16.57,14.34,35.92]
T=[1.22,1.58,2.16,2.92,1.90,7.23,3.70,17.32,51.77,72.47,74.82,91.20,5.21,7.10,9.04]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,s):p.write_text(s,encoding='utf-8',newline='\n')
def score(v):return sum(100/(1+math.log(a/b)/math.log(1.5)) for a,b in zip(v,T))/len(v)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--r08',type=Path);args=ap.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    image=OUT/'R08_user_screenshot.png'
    if not image.exists():
        if args.r08 is None:ap.error('--r08 screenshot required on first import')
        shutil.copyfile(args.r08,image)
    elif args.r08 is not None:assert sha(image)==sha(args.r08)
    previous=json.loads((ROOT/'V11_results/2026-09-26_r05_r06_submission/RESULT.json').read_text(encoding='utf-8'))
    times={k:[r[k+'_us'] for r in previous['rows']] for k in ['R04','R05','R06']};times['R08']=R08
    manifest=json.loads((ROOT/'BMMS_V11_R07_R08/MANIFEST.json').read_text(encoding='utf-8'))
    sources={r['version']:r for r in manifest['variants']}
    for r in sources.values():assert sha(ROOT/'BMMS_V11_R07_R08'/r['file'])==r['sha256']
    rows=[{'case':i+1,**{k+'_us':v[i] for k,v in times.items()},'T_us':T[i],
           'R08_vs_R04_time_delta_pct':100*(R08[i]/times['R04'][i]-1)} for i in range(15)]
    evidence={'R07':{'explicit_user_label':True,'status':'TLE','failed_case':5,'failure_stage':'runtime',
                     'evidence':'user text: 这是r08。r07 TLE了; clarification: 点5 运行阶段',
                     'local_source_sha256':sources['R07']['sha256'],'platform_source_digest_available':False,
                     'runtime_log_available':False,'root_cause_confirmed':False,'score':None},
              'R08':{'explicit_user_label':True,'status':'Pass','pass_count':15,'case_count':15,
                     'local_source_sha256':sources['R08']['sha256'],'platform_source_digest_available':False,
                     'screenshot_sha256':sha(image),'displayed_error_pct':[0.00]*15,'times_us':R08}}
    result={'evidence':evidence,'T_us':T,'T5_previous':1.95,'T5_current':1.90,
            'scores_same_current_T':{k:score(v) for k,v in times.items()},'rows':rows,
            'single_observation_per_version':True,'noise_removed':False,'statistically_proven_speedup':False,
            'provisional_working_parent':'R08','frozen_historical_control':'R04'}
    write(OUT/'RESULT.json',json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    with (OUT/'measurements.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    score_table='\n'.join(f'| {k} | {v:.6f} |' for k,v in result['scores_same_current_T'].items())
    table='\n'.join(f'| {r["case"]} | {r["R04_us"]:.2f} | {r["R05_us"]:.2f} | {r["R06_us"]:.2f} | {r["R08_us"]:.2f} | {r["T_us"]:.2f} | {r["R08_vs_R04_time_delta_pct"]:+.2f}% |' for r in rows)
    write(OUT/'AUDIT.md',f'''# R07 / R08平台反馈

用户明确确认R08为截图版本，15/15 Pass，误差栏显示0.00%（舍入显示，不是严格零误差证明）。
用户另行确认R07在点5运行阶段TLE。没有点5输入shape、设备故障日志或平台源码hash。
因此R07不能计为通过或有有效总分，也不能从TLE文字直接断言host搜索或设备死锁为根因。
本地提交源码与截图SHA保留在RESULT.json；历史包保持原字节。

| 版本 | 按最新T复算分数 |
|---|---:|
{score_table}

本次T5从1.95降至1.90μs。分数全用同一组最新T复算，旧截图本身不改写。

| 点 | R04 μs | R05 μs | R06 μs | R08 μs | 最新T μs | R08对R04耗时变化 |
|---|---:|---:|---:|---:|---:|---:|
{table}

点13从18.90到16.57μs，点14从15.28到14.34μs，是值得复核的局部改善。
其他多点变化接近此前提交的波动，但各版本仅一次观测，没有相邻同版控制复测，不能
据此估计置信区间或事后“排除噪声”。也没有公开shape证明点13/14必然走小K分支。

R08暂作下一轮开发父版，含义是已通过并有正向观测，不是统计意义上已证实最佳。
R04仍保留作历史控制；R07停止直接沿用，不在R08上合并其四轮任务网格搜索。
下一轮分别验证R09残余大K输出成包与R10单任务网格，附字节相同的R08控制。
建议R08→R09→R08，随后R10→R08；若R10仍超时，只记录失败，不升级或叠加。
每点比较候选与相邻控制的原始耗时，不做全局缩放、不拼接逐点最佳值。
''')
    print(json.dumps(result['scores_same_current_T'],indent=2))
if __name__=='__main__':main()

"""Retain qualitative R09 feedback and the representative, user-labelled R10 run."""
from pathlib import Path
import argparse,csv,hashlib,json,math,shutil
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;OUT=ROOT/'V11_results/2026-09-26_r09_r10_submission'
TIMES=[2.63,5.54,5.27,6.44,7.49,14.52,10.73,92.14,70.81,84.10,135.77,123.63,16.86,14.26,37.49]
T=[1.22,1.58,2.16,2.92,1.90,7.23,3.70,17.32,51.77,72.47,74.82,91.20,5.21,7.09,9.04]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,s):p.write_text(s,encoding='utf-8',newline='\n')
def score(v):return sum(100/(1+math.log(a/b)/math.log(1.5)) for a,b in zip(v,T))/15
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--r10',type=Path);args=ap.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    image=OUT/'R10_user_screenshot.png'
    if not image.exists():
        if args.r10 is None:ap.error('--r10 required on first import')
        shutil.copyfile(args.r10,image)
    elif args.r10 is not None:assert sha(image)==sha(args.r10)
    previous=json.loads((ROOT/'V11_results/2026-09-26_r07_r08_submission/RESULT.json').read_text(encoding='utf-8'))
    times={k:[r[k+'_us'] for r in previous['rows']] for k in ['R04','R05','R06','R08']};times['R10']=TIMES
    manifest=json.loads((ROOT/'BMMS_V11_R09_R10/MANIFEST.json').read_text(encoding='utf-8'))
    sources={r['version']:r for r in manifest['variants']}
    for r in sources.values():assert sha(ROOT/'BMMS_V11_R09_R10'/r['file'])==r['sha256']
    rows=[{'case':i+1,**{k+'_us':v[i] for k,v in times.items()},'T_us':T[i],
           'R10_vs_R08_time_delta_pct':100*(TIMES[i]/times['R08'][i]-1)} for i in range(15)]
    evidence={'R09':{'feedback_type':'qualitative_user_report','user_statement':'r09没啥收益',
                     'local_source_sha256':sources['R09']['sha256'],'platform_source_digest_available':False,
                     'timings_available':False,'pass_count':None,'score':None,'decision':'do not merge'},
              'R10':{'explicit_user_label':True,'user_statement':'r10收益稳定且明显 典型如下',
                     'status':'Pass','pass_count':15,'case_count':15,'local_source_sha256':sources['R10']['sha256'],
                     'platform_source_digest_available':False,'screenshot_sha256':sha(image),'times_us':TIMES,
                     'displayed_error_pct':[0.00]*15,'user_reports_stable_benefit':True,
                     'quantitative_screenshots_received':1,'repeat_count_available':False,
                     'raw_repeat_samples_available':False}}
    result={'evidence':evidence,'T_us':T,'T14_previous':7.10,'T14_current':7.09,
            'scores_same_current_T':{k:score(v) for k,v in times.items()},'rows':rows,
            'working_baseline':'R10','statistical_confidence_interval_available':False,
            'R07_runtime_case5_TLE_root_cause_confirmed':False}
    write(OUT/'RESULT.json',json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    with (OUT/'measurements.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    table='\n'.join(f'| {r["case"]} | {r["R08_us"]:.2f} | {r["R10_us"]:.2f} | {r["T_us"]:.2f} | {r["R10_vs_R08_time_delta_pct"]:+.2f}% |' for r in rows)
    scores='\n'.join(f'| {k} | {v:.6f} |' for k,v in result['scores_same_current_T'].items())
    write(OUT/'AUDIT.md',f'''# R09 / R10平台反馈：保留R10，R09不合并

用户明确报告R09没有明显收益，R10收益稳定且明显，并提供一张典型R10截图。
R10截图15/15 Pass，0.00%为误差栏舍入显示。尊重用户复测结论，将R10升级为工作基线；
同时区分证据：只有一份逐点原始截图，没有重复次数、全部样本或置信区间。
R09没有提供截图/耗时，不虚构其分数、通过点数或退化幅度。

| 版本 | 按本轮T复算 |
|---|---:|
{scores}

T14由7.10降到7.09μs。各版使用同一最新T，旧图和旧记录保持原样。

| 点 | R08 μs | R10典型值 μs | 最新T μs | R10对R08耗时变化 |
|---|---:|---:|---:|---:|
{table}

点10下降106.62→84.10μs（−21.12%，约1.268倍速度）。其他多点接近历史波动范围；
点15这张图变慢，不把它忽略或用历史最短值替换。完整总分用本张图全部15点计算。

R10与R08的device源码相同，只改变宏块host网格；结合用户报告的稳定改善，说明任务分配
是值得继续的方向。这里是源码差异和观测支持的判断，没有profiler证实具体流水瓶颈，
也未获得隐藏点shape。不能推断R07点5TLE根因已被排除或修复。

后续分别验证R11消除符合条件的短第二轮任务，以及R12并行合并N分片。
两版独立从R10派生，不包含用户反馈收益不明显的R09。提交包附冻结R10控制。
仍建议候选前后穿插R10，按逐点原始耗时比较，统一最新T计分，不拼接最佳点。
''')
    print(json.dumps(result['scores_same_current_T'],indent=2))
if __name__=='__main__':main()

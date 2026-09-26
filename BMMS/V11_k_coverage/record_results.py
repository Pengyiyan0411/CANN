"""Keep original labelled images and compare every version using the same current T."""
from pathlib import Path
import argparse,csv,hashlib,json,math,shutil
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;OUT=ROOT/'V11_results/2026-09-26_r13_r14_submission'
TIMES={'R13':[2.61,5.34,5.28,6.35,7.11,14.69,10.75,91.66,69.67,84.37,100.68,123.91,17.02,14.45,35.85],
       'R14':[2.56,5.40,5.20,6.28,7.20,14.15,10.44,91.18,69.13,83.96,100.56,123.11,16.31,13.90,36.25]}
T=[1.22,1.58,2.16,2.92,1.90,7.09,3.70,14.88,51.77,72.47,74.82,91.20,5.20,5.40,9.04]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,s):p.write_text(s,encoding='utf-8',newline='\n')
def score(v):return sum(100/(1+math.log(a/b)/math.log(1.5)) for a,b in zip(v,T))/15
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--r13',type=Path);ap.add_argument('--r14',type=Path);args=ap.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    previous=json.loads((ROOT/'V11_results/2026-09-26_r11_r12_submission/RESULT.json').read_text(encoding='utf-8'))
    assert previous['T_us']==T
    times={k:[r[k+'_us'] for r in previous['rows']] for k in previous['scores_same_current_T']};times.update(TIMES)
    manifest=json.loads((ROOT/'BMMS_V11_R13_R14/MANIFEST.json').read_text(encoding='utf-8'));evidence={}
    for r in manifest['variants']:
        v=r['version'];image=OUT/(v+'_user_screenshot.png');arg=getattr(args,v.lower())
        assert sha(ROOT/'BMMS_V11_R13_R14'/r['file'])==r['sha256']
        if not image.exists():
            if arg is None:ap.error('--'+v.lower()+' required on first import')
            shutil.copyfile(arg,image)
        elif arg is not None:assert sha(image)==sha(arg)
        evidence[v]={'explicit_user_label':True,'conversation_image_index':2 if v=='R13' else 1,
            'status':'Pass','pass_count':15,'case_count':15,'local_source_sha256':r['sha256'],
            'platform_source_digest_available':False,'screenshot_sha256':sha(image),
            'times_us':TIMES[v],'displayed_error_pct':[0.0]*15,'quantitative_screenshots_received':1,
            'raw_repeat_samples_available':False,'user_reports_stable_benefit':None}
    rows=[{'case':i+1,**{k+'_us':v[i] for k,v in times.items()},'T_us':T[i],
        **{v+'_vs_R11_time_delta_pct':100*(TIMES[v][i]/times['R11'][i]-1) for v in TIMES}} for i in range(15)]
    result={'evidence':evidence,'T_us':T,'T_changes':[],
        'scores_same_current_T':{k:score(v) for k,v in times.items()},'rows':rows,'working_baseline':'R11',
        'R13_R14_decision':'do not merge yet; small single-screenshot differences without paired controls',
        'statistical_confidence_interval_available':False,'adjacent_same_version_controls_available':False,
        'R07_runtime_case5_TLE_root_cause_confirmed':False}
    write(OUT/'RESULT.json',json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    with (OUT/'measurements.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    points='\n'.join(f'| {r["case"]} | {r["R11_us"]:.2f} | {r["R13_us"]:.2f} | {r["R14_us"]:.2f} | {r["T_us"]:.2f} | {r["R13_vs_R11_time_delta_pct"]:+.2f}% | {r["R14_vs_R11_time_delta_pct"]:+.2f}% |' for r in rows)
    scores='\n'.join(f'| {k} | {v:.6f} |' for k,v in result['scores_same_current_T'].items())
    write(OUT/'AUDIT.md',f'''# R13 / R14平台反馈：继续保留R11工作基线

用户明确图1为R14、图2为R13；两版均15/15 Pass，误差栏显示0.00%。T与上轮相同。
每版只有一张截图，无相邻R11控制或重复样本，不能构造置信区间或声称稳定收益。

| 版本 | 同本次T复算分数 |
|---|---:|
{scores}

| 点 | R11 μs | R13 μs | R14 μs | T μs | R13对R11耗时变化 | R14对R11耗时变化 |
|---|---:|---:|---:|---:|---:|---:|
{points}

R11/R13/R14点10为83.75/84.37/83.96μs，点11为100.71/100.68/100.56μs，
未出现R10、R11那样的大幅改善。R14部分点较快、R13部分点较慢，但没有足够证据排除
平台波动；不全局比例去噪，不拼接最短点，不把分数小幅增加当作优化已经有效。
R13/R14保持独立冻结，不合入R11。下一轮检查此前未覆盖的规则K形状，避免继续仅调网格。

源码SHA绑定本地已交付文件，截图身份来自用户明确标签；平台未提供提交源码摘要。
R07点5运行TLE根因未知、3项离线极端数值限制尚未修复。0.00%不等价于逐位一致。
''')
    print(json.dumps({'scores':result['scores_same_current_T'],'T_changes':[]},indent=2))
if __name__=='__main__':main()

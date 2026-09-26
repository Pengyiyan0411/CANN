"""Archive explicitly labelled R12 (image 1) and R11 (image 2) platform results."""
from pathlib import Path
import argparse,csv,hashlib,json,math,shutil
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;OUT=ROOT/'V11_results/2026-09-26_r11_r12_submission'
TIMES={'R11':[2.78,5.28,5.30,6.41,7.10,13.96,10.52,92.22,70.35,83.75,100.71,123.27,16.58,14.08,37.07],
       'R12':[2.70,5.51,5.46,6.45,7.12,14.21,10.61,91.04,70.07,84.77,135.49,123.56,16.53,14.15,36.24]}
T=[1.22,1.58,2.16,2.92,1.90,7.09,3.70,14.88,51.77,72.47,74.82,91.20,5.20,5.40,9.04]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,s):p.write_text(s,encoding='utf-8',newline='\n')
def score(v,t=T):return sum(100/(1+math.log(a/b)/math.log(1.5)) for a,b in zip(v,t))/15
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--r11',type=Path);ap.add_argument('--r12',type=Path);args=ap.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    previous=json.loads((ROOT/'V11_results/2026-09-26_r09_r10_submission/RESULT.json').read_text(encoding='utf-8'))
    times={k:[r[k+'_us'] for r in previous['rows']] for k in ['R04','R05','R06','R08','R10']};times.update(TIMES)
    manifest=json.loads((ROOT/'BMMS_V11_R11_R12/MANIFEST.json').read_text(encoding='utf-8'))
    evidence={}
    for r in manifest['variants']:
        version=r['version'];image=OUT/(version+'_user_screenshot.png');arg=getattr(args,version.lower())
        assert sha(ROOT/'BMMS_V11_R11_R12'/r['file'])==r['sha256']
        if not image.exists():
            if arg is None:ap.error('--'+version.lower()+' required on first import')
            shutil.copyfile(arg,image)
        elif arg is not None:assert sha(image)==sha(arg)
        evidence[version]={'explicit_user_label':True,'conversation_image_index':2 if version=='R11' else 1,
            'status':'Pass','pass_count':15,'case_count':15,'local_source_sha256':r['sha256'],
            'platform_source_digest_available':False,'screenshot_sha256':sha(image),
            'times_us':TIMES[version],'displayed_error_pct':[0.0]*15,
            'quantitative_screenshots_received':1,'raw_repeat_samples_available':False,
            'user_reports_stable_benefit':None}
    rows=[{'case':i+1,**{k+'_us':v[i] for k,v in times.items()},'T_us':T[i],
        'R11_vs_R10_time_delta_pct':100*(TIMES['R11'][i]/times['R10'][i]-1),
        'R12_vs_R10_time_delta_pct':100*(TIMES['R12'][i]/times['R10'][i]-1)} for i in range(15)]
    changes=[{'case':i+1,'previous':a,'current':b} for i,(a,b) in enumerate(zip(previous['T_us'],T)) if a!=b]
    result={'evidence':evidence,'T_us':T,'T_changes':changes,
        'scores_same_current_T':{k:score(v) for k,v in times.items()},'rows':rows,
        'working_baseline':'R11','R11_benefit_observed_not_repeatedly_confirmed':True,
        'R12_decision':'do not merge; no clear improvement distinguishable from observed submission variation',
        'statistical_confidence_interval_available':False,'adjacent_same_version_controls_available':False,
        'R07_runtime_case5_TLE_root_cause_confirmed':False}
    write(OUT/'RESULT.json',json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    with (OUT/'measurements.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    points='\n'.join(f'| {r["case"]} | {r["R10_us"]:.2f} | {r["R11_us"]:.2f} | {r["R12_us"]:.2f} | {r["T_us"]:.2f} | {r["R11_vs_R10_time_delta_pct"]:+.2f}% |' for r in rows)
    scores='\n'.join(f'| {k} | {v:.6f} |' for k,v in result['scores_same_current_T'].items())
    tchanges='、'.join(f'点{r["case"]} {r["previous"]:.2f}→{r["current"]:.2f}' for r in changes)
    write(OUT/'AUDIT.md',f'''# R11 / R12平台反馈：R11作为工作基线，R12暂不合并

用户明确标注图1为R12、图2为R11，两图均15/15 Pass、误差栏显示0.00%。
每版只有一张逐点截图，未给重复次数或相邻R10控制；不能沿用上轮R10的稳定性确认来
声称R11已经复测稳定。R11点11的大幅改善足以作为继续开发依据，R10仍冻结可回退。

| 版本 | 同本次T复算分数 |
|---|---:|
{scores}

本次T变化：{tchanges}μs。T是当前最优性能，不是本次提交耗时；统一T后才能比较
跨轮总分。旧图和旧结果不改写，不把对手T下降误认成自己的内核退化。

| 点 | R10 μs | R11 μs | R12 μs | 本次T μs | R11对R10耗时变化 |
|---|---:|---:|---:|---:|---:|
{points}

R11点11为135.77→100.71μs（−25.82%）；同轮R12点11为135.49μs，亦明显慢于R11。
点10为83.75μs，与R10的84.10μs接近，保留上轮主要收益。其他小幅变化暂按未分辨处理，
不做全局比例去噪，不拼接各版最短点。R12未显示同量级正向变化，当前不合并。

R11仅改宏块host网格，R12独立只改末段N合并。这些观测支持继续改善任务分配；
没有hidden shape或profiler，不能确定各点分支，也不能证明N合并完全没有性能占比。
后续R13/R14独立从R11派生，分别检查短第二轮和已有单轮能否使用略少核组来降低峰值。
原有3项极端精度限制及R07点5运行TLE根因未知的状态保持不变。
''')
    print(json.dumps({'scores':result['scores_same_current_T'],'T_changes':changes},indent=2))
if __name__=='__main__':main()

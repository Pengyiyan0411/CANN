"""Archive explicitly labelled R01 screenshot and score each case consistently."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math
import shutil

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'V11_results/2026-09-26_r01_submission'
R01=[2.63,5.34,5.59,6.31,7.67,14.88,13.82,92.98,80.63,121.95,148.88,140.57,19.12,15.30,115.13]
P01=[2.41,5.57,5.23,6.50,7.19,14.41,12.83,90.82,119.83,141.21,171.70,108.87,17.92,14.99,110.22]
D01=[2.54,5.93,5.22,6.52,7.42,14.86,11.18,91.56,129.99,179.45,303.93,294.81,18.88,14.92,37.54]
F01=[11.16,11.85,9.88,12.30,10.20,17.44,15.11,138.17,182.53,257.41,320.81,285.61,35.13,204.04,31.17]
T=[1.22,1.58,2.16,2.92,2.36,7.23,3.70,17.32,52.01,72.47,74.82,91.20,5.21,7.10,9.04]
def item(x,t):return 100/(1+math.log(x/t)/math.log(1.5))
def score(xs):return sum(item(x,t) for x,t in zip(xs,T))/15
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--screenshot',type=Path);args=ap.parse_args()
    OUT.mkdir(parents=True,exist_ok=True);image=OUT/'R01_user_screenshot.png'
    if not image.exists():
        if args.screenshot is None:ap.error('--screenshot required on first import')
        shutil.copyfile(args.screenshot,image)
    source=ROOT/'BMMS_V11_SubmitPack/R01_REUSE_2X2.asc'
    assert sha(source)=='dc372a48a8b38dcb3ee1c782f93842624945cfe0627b04b2112e70d0a949663e'
    rows=[{'case':i+1,'status':'Pass','display_error':'0.00%','r01_us':r,'p01_historical_us':p,
        'd01_us':d,'F01_us':f,'T_us':t,'p01_over_r01':p/r,'score_delta_contribution':(item(r,t)-item(p,t))/15}
        for i,(r,p,d,f,t) in enumerate(zip(R01,P01,D01,F01,T))]
    with (OUT/'measurements.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    result={'variant':'R01_REUSE_2X2','identity':'explicit user label R01; platform source digest unavailable',
        'local_source_sha256':sha(source),'screenshot_sha256':sha(image),'pass_count':15,'case_count':15,
        'ui_error_is_rounded':True,'scores_same_T':{k:score(xs) for k,xs in [('R01',R01),('P01_historical',P01),('D01',D01),('F01',F01)]},
        'r01_minus_p01':score(R01)-score(P01),'r01_minus_f01':score(R01)-score(F01),
        'case_9_11_gain':sum(r['score_delta_contribution'] for r in rows[8:11]),
        'case_12_delta':rows[11]['score_delta_contribution'],'rows':rows,
        'paired_baseline_same_session':False,'hidden_shapes_known':False,'profiler_available':False,
        'next_experiments':['R02 macro output publication only','R03 R01 then D01 residual domain only'],
        'environment':'user has no NPU environment; continue via platform submissions'}
    (OUT/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    table='\n'.join(f'| {r["case"]} | {r["r01_us"]:.2f} | {r["p01_historical_us"]:.2f} | {r["d01_us"]:.2f} | {r["T_us"]:.2f} | {r["score_delta_contribution"]:+.5f} |' for r in rows)
    report=f'''# R01已确认：有局部收益，尚未超过P01

用户明确标注“R01”，15/15 Pass。源hash `{sha(source)}`，截图原件与hash已保存。
平台没有源hash/shape/kernel/profiler；0.00%是显示值，不证明逐位一致。
本轮用户再次说明没有测试环境，继续用提交推进。

| 版本 | 同T复算分数 |
|---|---:|
| P01历史 | {score(P01):.6f} |
| R01 | {score(R01):.6f} |
| D01 | {score(D01):.6f} |
| F01 | {score(F01):.6f} |

R01比P01历史低{score(P01)-score(R01):.6f}分，比F01高{score(R01)-score(F01):.6f}分。
P01未同轮重测，以下对比是历史参照，不能估计测量显著性。

| 点 | R01 μs | P01历史 μs | D01 μs | T μs | R01-P01总分贡献 |
|---|---:|---:|---:|---:|---:|
{table}

## 从结果得到什么

- 点9由119.83→80.63μs（约1.486×），点10/11约1.158×/1.153×。
  三项合计+{result['case_9_11_gain']:.6f}分，支持保留宏块复用继续验证。
- 点12由108.87→140.57μs，耗时增加约29.12%，单点损失
  {abs(result['case_12_delta']):.6f}分。不能用“其他大点变快”掩盖总分未胜出。
- 点15仍为115.13μs，D01为37.54μs。覆盖域差异是优先检查项，但时间相似不能
  证明点15实际走P01，也不能按该编号硬编码路由。
- 点1–8/13–14多数变化较小且非同轮A/B，暂不根据几个百分点变动改专用分支。

## 两个独立下一版

**R02_MACRO_RING**：R01每宏块4个C结果共用两个微块GM槽，存在宏块内部等待。
扩大为两个宏块槽，4个Fixpipe之后发1次READY，两AIV读完整宏块才FREE。
输入复用、调度、算术均保持，代价为ring空间4倍和更晚的首次消费。这是性能假设，
不宣称点12已定位或必然恢复。

**R03_RESIDUAL_DENSE**：完整保留R01，在其未覆盖但D01能处理的公开shape差集
上补D01 K128路径；小输出增加PIPE_M依赖。不包含R02改动，不抢R01已覆盖形状。
目的是验证覆盖不足，不把15号点当作分支条件。

两版先分别提交，暂不组合。所有本地检查仍是CPU模型；已知极端数值限制保留。
设计、资源和检查方法见 [后续设计](../../V11_followup/DESIGN.md)。
'''
    (OUT/'AUDIT.md').write_text(report,encoding='utf-8',newline='\n')
    print(json.dumps({k:result[k] for k in ['scores_same_T','r01_minus_p01','case_9_11_gain','case_12_delta']}))

if __name__=='__main__':main()

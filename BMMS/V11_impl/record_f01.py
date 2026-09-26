"""Preserve user-confirmed F01 screenshot and reproducible same-T comparison."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math
import shutil

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'V10_results/2026-09-26_f01_submission'
F01=[11.16,11.85,9.88,12.30,10.20,17.44,15.11,138.17,182.53,257.41,320.81,285.61,35.13,204.04,31.17]
P01=[2.41,5.57,5.23,6.50,7.19,14.41,12.83,90.82,119.83,141.21,171.70,108.87,17.92,14.99,110.22]
T=[1.22,1.58,2.16,2.92,2.36,7.23,3.70,17.32,52.01,72.47,74.82,91.20,5.21,7.10,9.04]
def score(ts):return sum(100/(1+math.log(x/t,1.5)) for x,t in zip(ts,T))/len(T)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--screenshot',type=Path);args=ap.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    dest=OUT/'F01_user_screenshot.png'
    if not dest.exists():
        if args.screenshot is None:ap.error('--screenshot is required when the archived image is absent')
        shutil.copyfile(args.screenshot,dest)
    source=ROOT/'BMMS_V10_SubmitPack/F01_STREAM_M.asc'
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    assert digest=='82bc0f92d9eb1ffdb092d5fb076e43f05080f62859e64e2b0a66e52c770b930c'
    rows=[dict(case=i+1,pass_status='Pass',display_error='0.00%',f01_us=x,p01_historical_us=p,T_us=t,f01_over_p01=x/p)
          for i,(x,p,t) in enumerate(zip(F01,P01,T))]
    with (OUT/'measurements.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    record={'variant':'F01_STREAM_M','identity':'explicitly confirmed by user; platform source hash unavailable',
        'local_source_sha256':digest,'screenshot_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),
        'pass_count':15,'case_count':15,'ui_error_is_rounded':True,'rows':rows,
        'score_formula':'mean(100 / (1 + log(time/T)/log(1.5)))',
        'f01_score_same_T':score(F01),'p01_historical_score_same_T':score(P01),
        'delta':score(F01)-score(P01),'regressed_cases':sum(x>p for x,p in zip(F01,P01)),
        'paired_same_run_baseline':False,'hidden_shapes_known':False,'profiler_available':False,
        'decision':'retire F01 as global mainline; F02 remains untested; rebuild dense route on P01 fallbacks'}
    (OUT/'RESULT.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    table='\n'.join(f'| {r["case"]} | {r["f01_us"]:.2f} | {r["p01_historical_us"]:.2f} | {r["T_us"]:.2f} | {r["f01_over_p01"]:.3f}× |' for r in rows)
    doc=f'''# F01 已确认结果与路线复审

用户明确确认截图对应 **F01_STREAM_M**；15/15 Pass，显示误差0.00%。
当地源文件 SHA256 `{digest}`。平台未提供源 hash，身份依据为用户确认。
显示误差为四舍五入结果，不证明逐位相等。没有隐藏 shape 或实际 kernel 信息。

相同 T 复算：F01 **{score(F01):.6f}**，P01历史 **{score(P01):.6f}**，
差 **{score(F01)-score(P01):.6f}**。P01不是同轮重测，不能当作严格A/B。
14/15点退化；点14达13.6117倍。点15相对P01加速约3.5361倍，不能据此
反推其shape或直接按隐藏编号拼接最优成绩。

| 点 | F01 μs | P01历史 μs | 同组 T μs | F01/P01 |
|---|---:|---:|---:|---:|
{table}

## 结论与下一步

1. 用户认为整体路线有问题是有数据支持的。F01的全域统一路径不能继续作为主线。
2. 代码静态证据：F01移除了P01的小规模专用路由，仍逐输出块同步SDK；
   V9的宏分组没有L1/L0操作数跨输出复用。截图无法单独证明哪项是每一点的根因。
3. 保留P01的公开shape分支，V11 R01仅替换有足够宏块并行度的密集计算。
   R01用128×256宏块共享输入、K1=256/K0=64。性能待测，不再把无完整C分配
   作为新收益。F02没有结果，停止盲目推进它不等于断言它一定慢。
4. 需要一次有截止时间的P01/R01真机检查，记录kernel和PipeUtilization。
   这比继续仅凭15个时间数字猜瓶颈有信息增益。无卡阶段先交源码、离线证据和脚本。

新路线、资源与取舍见 [V11设计](../../V11_impl/DESIGN.md)。
完整核、真实精度和性能必须由CANN/设备验证；已有FP32数值极端反例仍保留。
'''
    (OUT/'AUDIT.md').write_text(doc,encoding='utf-8')
    print(json.dumps({k:record[k] for k in ['variant','f01_score_same_T','p01_historical_score_same_T','delta','regressed_cases']},ensure_ascii=False))

if __name__=='__main__':main()

"""Archive user-labelled D01/S01 screenshots; no device invocation."""
from pathlib import Path
import argparse
import copy
import csv
import hashlib
import json
import math
import shutil
import record_results as scoring

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'V9_results'/'2026-09-26_first_submission'
CURRENT_T=[1.22,1.58,2.16,2.92,2.36,7.23,3.70,17.32,52.01,72.47,74.82,91.20,5.21,7.10,9.04]
OBSERVATIONS=[
    ('D01_DENSE_K128',[2.54,5.93,5.22,6.52,7.42,14.86,11.18,91.56,129.99,179.45,303.93,294.81,18.88,14.92,37.54],
     'cd72458717d92d057ef6548a82111cbd.png'),
    ('S01_SMALL_NT_PAIR',[2.34,5.80,5.22,6.42,7.33,14.58,13.60,92.28,121.44,142.60,169.98,110.66,19.29,15.10,112.75],
     '8cc76a7956c429761eb0ff561ea3e9b8.png')]


def score(times,refs):return sum(100/(1+math.log(s/t,1.5)) for s,t in zip(times,refs))/len(times)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write_json(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--images-dir',type=Path,help='Original screenshots, only needed for initial ingestion')
    args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((ROOT/'BMMS_V9_SubmitPack/MANIFEST.json').read_text(encoding='utf-8'))
    summary={'evidence':'User screenshots, explicitly labelled D01 and S01',
        'record_date':'2026-09-26','submission_ids_provided':False,
        'platform_source_hash_provided':False,'local_npu_run':False,
        'current_T_from_both_screenshots':CURRENT_T,
        'historical_T':scoring.T,'historical_P01_latency_us':scoring.P01,
        'P01_score_historical_T':score(scoring.P01,scoring.T),
        'P01_score_current_T':score(scoring.P01,CURRENT_T),'observations':[]}
    comparison=[]
    for variant,times,original_image_name in OBSERVATIONS:
        source=next(v for v in manifest['variants'] if v['id']==variant)
        assert sha(ROOT/'BMMS_V9_SubmitPack'/source['file'])==source['sha256']
        image_name=variant+'.png'
        if not (OUT/image_name).exists():
            if args.images_dir is None:raise ValueError('Initial ingestion requires --images-dir')
            shutil.copyfile(args.images_dir/original_image_name,OUT/image_name)
        data={'variant':variant,'submission_id':None,'compile_error':None,
              'source_binding':'User identified filename; SHA is local packaged source, not platform-verified',
              'reported_execution':'15/15 Pass screenshot; raw compilation logs not supplied',
              'screenshot':image_name,'screenshot_sha256':sha(OUT/image_name),
              'error_display':'0.00% on each row; rounded display, not exact-error proof',
              'rows':[{'case':i+1,'status':'Pass','latency_us':v,'best_us':CURRENT_T[i]} for i,v in enumerate(times)]}
        result=scoring.analyze(copy.deepcopy(data),manifest)
        result['score_historical_T']=score(times,scoring.T)
        result['delta_score_vs_P01_current_T']=result['computed_score']-summary['P01_score_current_T']
        for row,t,p in zip(result['rows'],CURRENT_T,scoring.P01):
            row['mean_score_delta_vs_P01']=(100/(1+math.log(row['latency_us']/t,1.5))-100/(1+math.log(p/t,1.5)))/15
            comparison.append({'variant':variant,**row})
        write_json(OUT/(variant+'.json'),result)
        summary['observations'].append({k:result[k] for k in ['variant','source_sha256','all_15_pass','computed_score','score_historical_T','delta_score_vs_P01_current_T']})
    write_json(OUT/'summary.json',summary)
    with (OUT/'per_case_comparison.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(comparison[0]));writer.writeheader();writer.writerows(comparison)
    lines=['# V9 D01 / S01 首轮平台结果审计','',
        '记录日期：2026-09-26。用户明确标注图一 D01、图二 S01；两图均为15/15 Pass。未提供提交编号、原始编译日志、平台源码hash或重复测量。归档hash对应本地此前交付文件，身份绑定依据用户文件名确认。','',
        '## 同一 T 下比较','',
        '| 版本 | 当前截图 T 复算 | 相对历史 P01 同 T | 状态 |',
        '|---|---:|---:|---|',f'| P01历史耗时 | {summary["P01_score_current_T"]:.4f} | — | 非同轮重测 |']
    for r in summary['observations']:
        lines.append(f'| {r["variant"]} | {r["computed_score"]:.4f} | {r["delta_score_vs_P01_current_T"]:+.4f} | 本轮15/15 |')
    lines+=['',
        'T有三处变化：点5从2.38到2.36，点13从9.37到5.21，点14从10.11到7.10 μs。同一P01耗时在旧T下34.0599，在新T下32.0956；不能把基准更新造成的降分算作代码退化。上述分数按截图两位小数耗时复算，未冒充平台显示总分。','',
        '## 逐点原始用时','',
        '| 点 | P01历史μs | D01 μs | S01 μs | 当前T μs |',
        '|---:|---:|---:|---:|---:|']
    for i,(p,d,s,t) in enumerate(zip(scoring.P01,OBSERVATIONS[0][1],OBSERVATIONS[1][1],CURRENT_T),1):
        lines.append(f'| {i} | {p:.2f} | {d:.2f} | {s:.2f} | {t:.2f} |')
    lines+=['','## 判断与下一步','',
        '- D01的点15从110.22降至37.54 μs，约2.94倍加速；点7下降12.86%。原生路径存在值得保留的局部收益，但不能由耗时反推隐藏shape或断言实际命中。',
        '- D01点10/11/12较P01分别慢27.08%、77.01%、170.79%。点12单独拉低均分约2.9278，超过点15带来的约0.5477。停止把D01作为全域替换候选，保留源码作诊断。',
        '- S01没有显示整体收益，暂缓组合M01。结果近似P01不能证明S分支没有触发；没有路由日志，未命中、命中后性能接近及测量波动均未排除。',
        '- 下一次优先提交已交付D02_DENSE_K64.asc，只改变K块大小，判断D01退化是否对K stage敏感。它不是预期大幅涨分的保证。不要把组合版当作下一轮默认选择。',
        '- 若D02仍有大幅退化，dense主线应转向输入复用、L1/L0两级流水及消费者开销的结构改造；不能只继续扫K/pM/pN参数。形状分流须依据公开输入和可检验的成本模型，不按测试编号选版本。','',
        '## 精度与复现边界','',
        '两图确认本轮评测15点通过，支持这两个候选至少完成了平台构建与执行，但不认证全部模板实例化、所有合法形状或所有数值输入。每行0.00%是界面显示，不是逐位精确证明。既有强消减与BF16中间溢出反例继续保留，见../../V9_impl/precision_review.md。','',
        'JSON保留原始点耗时、当前T、归档源hash和各点得分贡献；CSV可直接重新核算。不修改原实验包的构建时MANIFEST，也不将构建时“尚未上卡”记录伪装成最新状态。当前状态以本报告和summary.json为准。','']
    (OUT/'AUDIT.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()

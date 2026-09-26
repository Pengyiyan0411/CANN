"""Record the user-labelled D02 screenshot and compare using one T snapshot."""
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
OUT=ROOT/'V9_results/2026-09-26_d02_submission'
TIMES=[2.49,5.38,5.09,6.48,7.53,15.10,11.81,91.95,226.52,216.94,465.89,295.49,18.88,15.53,52.47]
CURRENT_T=[1.22,1.58,2.16,2.92,2.36,7.23,3.70,17.32,52.01,72.47,74.82,91.20,5.21,7.10,9.04]


def write_json(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def score(times):return sum(100/(1+math.log(s/t,1.5)) for s,t in zip(times,CURRENT_T))/15


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--image',type=Path);args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    pic=OUT/'D02_DENSE_K64.png'
    if not pic.exists():
        if args.image is None:raise ValueError('Initial ingestion requires --image')
        shutil.copyfile(args.image,pic)
    manifest=json.loads((ROOT/'BMMS_V9_SubmitPack/MANIFEST.json').read_text(encoding='utf-8'))
    variant=next(v for v in manifest['variants'] if v['id']=='D02_DENSE_K64')
    assert hashlib.sha256((ROOT/'BMMS_V9_SubmitPack'/variant['file']).read_bytes()).hexdigest()==variant['sha256']
    prior=ROOT/'V9_results/2026-09-26_first_submission'
    d1=json.loads((prior/'D01_DENSE_K128.json').read_text(encoding='utf-8'))
    s1=json.loads((prior/'S01_SMALL_NT_PAIR.json').read_text(encoding='utf-8'))
    assert [r['best_us'] for r in d1['rows']]==CURRENT_T==[r['best_us'] for r in s1['rows']]
    data={'variant':variant['id'],'submission_id':None,'compile_error':None,
          'source_binding':'User identified D02; SHA is packaged local source, not platform-verified',
          'reported_execution':'15/15 Pass screenshot; raw compilation logs not supplied',
          'screenshot':pic.name,'screenshot_sha256':hashlib.sha256(pic.read_bytes()).hexdigest(),
          'error_display':'0.00% on each row; rounded display, not exact-error proof',
          'rows':[{'case':i+1,'status':'Pass','latency_us':v,'best_us':CURRENT_T[i]} for i,v in enumerate(TIMES)]}
    result=scoring.analyze(copy.deepcopy(data),manifest)
    for row,old,p in zip(result['rows'],d1['rows'],scoring.P01):
        row['D01_us']=old['latency_us'];row['relative_to_D01_percent']=(row['latency_us']/old['latency_us']-1)*100
    write_json(OUT/'D02_DENSE_K64.json',result)
    series={'P01_historical':scoring.P01,'D01':[r['latency_us'] for r in d1['rows']],
            'S01':[r['latency_us'] for r in s1['rows']],'D02':TIMES}
    summary={'record_date':'2026-09-26','current_T':CURRENT_T,'T_unchanged_from_first_submission':True,
             'scores_same_T':{name:score(values) for name,values in series.items()},
             'D02_all_15_pass':True,'local_npu_run':False,'submission_id_provided':False,
             'platform_source_digest_provided':False,
             'decision':'Retire K64 as the next baseline; keep P01 control; test D01 K128 with two L0C slots independently.'}
    write_json(OUT/'summary.json',summary)
    with (OUT/'per_case_comparison.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(result['rows'][0]));writer.writeheader();writer.writerows(result['rows'])
    lines=['# D02 平台结果与路线收敛','',
        '用户将本图标注为D02，15点均Pass。本报告按本地D02文件hash绑定，未得到平台源码hash、提交编号、逐点shape或route日志；P01是历史耗时，不是本轮复测。','',
        '## 相同T下复算','',
        '| 版本 | 分数 |','|---|---:|']
    for name,val in summary['scores_same_T'].items():lines.append(f'| {name} | {val:.4f} |')
    lines+=['','本图T与D01/S01截图完全相同。以上使用截图两位小数耗时复算，并非平台显示总分。','',
        '## 逐点对比','',
        '| 点 | P01 μs | D01 μs | D02 μs | D02较D01 | 当前T μs |',
        '|---:|---:|---:|---:|---:|---:|']
    for r in result['rows']:
        lines.append(f'| {r["case"]} | {r["p01_us"]:.2f} | {r["D01_us"]:.2f} | {r["latency_us"]:.2f} | {r["relative_to_D01_percent"]:+.2f}% | {r["best_us"]:.2f} |')
    lines+=['','## 可以收敛的判断','',
        '1. K128改成K64没有修复D01的大幅退化域。点9/10/11/15较D01分别慢74.26%/20.89%/53.29%/39.77%；停止继续向K32/48/96无方向扫参。',
        '2. 点12从294.81到295.49 μs，仅+0.23%，但仍约为历史P01的2.71倍。这说明该点没有因本次K粒度变化而恢复；不能因此直接断言具体shape、确定命中、带宽瓶颈或消费者独占瓶颈。',
        '3. 点15仍比历史P01快约2.10倍，D01则约2.94倍。原生路线仍保留局部收益信号，广泛替换的策略未成立；当前保持P01保底，M01暂缓。',
        '4. D02使K循环和部分事件次数增多，逻辑输入字节未减，结果与更密的搬运/指令/事件开销不利这一假设相容，但尚未区分三者，也不是硬件profiler证据。','',
        '## 下一份：D03，K128双L0C','',
        '以D01为唯一对照，把L0C从一个32KiB槽改成两个32KiB槽；第t个输出块用t%2，只在该槽再次使用前等待此前Fixpipe读完。保留输入搬运、K128、Plan、M/N路由、consumer和GM两槽协议。用于检验single-L0C的相邻计算/搬出依赖，不宣称已实现输入复用或保证提速。',
        '完整K累加顺序、FP32 C和Max/Sum保持原样，因此不会修复既有强消减反例。待平台编译、15点精度及用时验证。若点9–12仍不恢复，就不再围绕该等待做参数变体，推进真实M/N输入复用；若改善，再用同输入确认收益域。','',
        '本轮不申请额外NPU。后续若结构候选仍不能区分等待和搬运瓶颈，再申请短时profiling环境。源码CPU模型只用于内存、索引、信用计数和指定输入算术；不提供真实性能证据。','']
    (OUT/'AUDIT.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()

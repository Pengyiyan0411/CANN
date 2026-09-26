"""Record the unlabelled screenshot following D03; identity remains inferred."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import shutil
import record_results as scoring

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'V9_results/2026-09-26_d03_submission'
TIMES=[2.55,5.49,5.10,6.59,7.27,14.52,11.13,91.76,129.15,177.06,292.17,299.40,18.65,15.30,36.40]
T=[1.22,1.58,2.16,2.92,2.36,7.23,3.70,17.32,52.01,72.47,74.82,91.20,5.21,7.10,9.04]


def write_json(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def score(values):return sum(100/(1+math.log(x/t,1.5)) for x,t in zip(values,T))/15


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--image',type=Path);args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True);pic=OUT/'D03_context_inferred.png'
    if not pic.exists():
        if args.image is None:raise ValueError('Initial ingestion requires --image')
        shutil.copyfile(args.image,pic)
    m=json.loads((ROOT/'BMMS_V9_D03/MANIFEST.json').read_text(encoding='utf-8'))
    assert hashlib.sha256((ROOT/'BMMS_V9_D03'/m['file']).read_bytes()).hexdigest()==m['sha256']
    d1=json.loads((ROOT/'V9_results/2026-09-26_first_submission/D01_DENSE_K128.json').read_text(encoding='utf-8'))
    assert [r['best_us'] for r in d1['rows']]==T
    data={'variant':m['variant'],'submission_id':None,
          'identity_status':'CONTEXT_INFERRED_NOT_EXPLICITLY_LABELLED',
          'source_binding':'Screenshot follows D03 delivery; user did not explicitly label it. Packaged SHA is not platform-verified.',
          'reported_execution':'15/15 Pass screenshot; raw compilation logs absent',
          'screenshot':pic.name,'screenshot_sha256':hashlib.sha256(pic.read_bytes()).hexdigest(),
          'error_display':'0.00% each row is rounded UI output, not bitwise-accuracy evidence',
          'rows':[{'case':i+1,'status':'Pass','latency_us':v,'best_us':T[i]} for i,v in enumerate(TIMES)]}
    result=scoring.analyze(data,{'variants':[{'id':m['variant'],'sha256':m['sha256']}]})
    for row,prior in zip(result['rows'],d1['rows']):
        row['D01_us']=prior['latency_us'];row['relative_to_D01_percent']=(row['latency_us']/prior['latency_us']-1)*100
    write_json(OUT/'D03_context_inferred.json',result)
    summary={'identity_status':data['identity_status'],'T_unchanged':True,'all_15_pass':True,
             'scores_same_T':{'P01_historical':score(scoring.P01),'D01':d1['computed_score'],
                              'D02':26.864737035669968,'D03_context_inferred':result['computed_score']},
             'D03_minus_D01':result['computed_score']-d1['computed_score'],
             'decision':'Stop double-L0C variations; implement true B reuse with an M128/N128 producer and matching consumer.',
             'local_npu_run':False}
    write_json(OUT/'summary.json',summary)
    lines=['# D03 后续截图审计与D04决策','',
        '**版本身份为上下文推定。** 本图紧接D03交付，用户没有标明版本；先按D03分析，不把这一身份写成明确确认。15点Pass及耗时是截图可读事实，未提供提交号、平台源码hash或重复测量。','',
        '| 版本 | 同T复算分数 |','|---|---:|']
    for name,value in summary['scores_same_T'].items():lines.append(f'| {name} | {value:.4f} |')
    lines+=['','T与前两轮一致。P01为历史耗时，复算不是同轮重测，也不是平台显示总分。','',
        '| 点 | P01 μs | D01 μs | 本图 μs | 本图较D01 |',
        '|---:|---:|---:|---:|---:|']
    for r in result['rows']:lines.append(f'| {r["case"]} | {r["p01_us"]:.2f} | {r["D01_us"]:.2f} | {r["latency_us"]:.2f} | {r["relative_to_D01_percent"]:+.2f}% |')
    lines+=['','## 三轮实验得到的判断','',
        '1. D02缩K失败；D03双L0C相对D01也没有恢复点9–12。点12为299.40 μs，较D01反而+1.56%，仍为历史P01的约2.75倍。停止围绕K变小或C槽数继续扫描。',
        '2. 点11较D01改善3.87%、点15改善3.04%，但单轮小幅变化未排除运行波动，不能宣称双L0C已稳定提速；更不能解释为已找到主瓶颈。',
        '3. 原生分支在部分输入仍有收益信号，整体替换策略未成立。没有隐藏shape、route或profiler，不将点号映射成任何既定输入族。','',
        '## D04：扩大真实计算块，复用B','',
        '以D03为代码基础，把TM从64改128，TN=128、K stage=128、双L0C保留；producer和consumer一起改为128行消息。完整输出块内，一次载入的B给128行使用，减少M方向的B重读。AM256/BN512仍只是遍历分组，不虚构为常驻输入。',
        '这会改变M tile数量、空间分核、环区大小、每条消费消息行数和资源占用，是一组实现复用所需的协同变更。它不是只改host分流阈值，也不是已实现K1/K0分层或完整2×2 A/B复用。',
        '在B1,M256,N256,K256,cores1的公开控制场景，预计逻辑输入读取从768KiB降至512KiB，输出发布从8块降至4块，C总写读字节不变；将用真实源码模型计数核实。实际cache、HBM字节、占用率和用时仍必须上卡。','',
        '## 新发现的同步约束','',
        '官方Mmad文档和本地固定CATLASS v1.4.0的tile_mmad.hpp均规定：小输出块((m/16)*(n/16)<10)连续累加时需要PIPE_M屏障。此前D01–D03只有双输入槽的事件循环，没有显式实现这一条件。平台15点通过不能排除该同步边界；D04补上，不将它当作已证实的耗时根因。',
        '参考：[官方Mmad](https://asc.gitcode.com/api/SIMD-API/basic_api/cube_compute_ISASI/mmad_compute/Mmad.html)；该在线文档为开发版，固定CATLASS源码中同样有阈值10和屏障。此前FP32 C强消减数值反例继续存在。','',
        '当前P01保底。D04待平台编译、精度和时间结果，不申请额外NPU。若本图实际不是D03，应重新绑定版本并撤销基于D03的效果归因，原图和原始耗时保留。','']
    (OUT/'AUDIT.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()

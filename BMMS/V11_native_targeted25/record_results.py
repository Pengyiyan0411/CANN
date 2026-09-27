"""Archive the user-ordered N01..N05 screenshots without changing frozen D24."""
from pathlib import Path
import argparse,csv,hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'V11_results/2026-09-27_d24_native'
DATA={
'N01_K_EQ32':[2.62,5.43,4.99,6.28,7.49,14.96,11.10,90.43,69.92,84.54,101.65,124.90,17.15,14.56,15.14],
'N02_K_EQ64':[2.81,5.36,5.19,6.38,7.84,15.62,11.42,93.16,71.77,85.15,102.69,125.51,17.56,15.13,15.54],
'N03_M_LE32':[2.78,5.14,4.98,6.46,14.67,15.09,11.43,92.86,71.15,84.94,102.11,124.70,17.51,14.96,15.23],
'N04_N_LE32':[2.68,5.05,5.28,6.38,14.60,15.08,11.28,93.90,70.47,84.93,102.50,124.78,17.83,15.15,15.21],
'N05_B_EQ1':[2.60,5.42,5.30,6.59,7.58,14.46,11.30,92.24,70.20,84.29,101.30,123.29,98.42,43.23,15.08]}
BEST=[1.22,1.58,2.16,2.92,1.89,7.09,3.70,14.88,51.77,72.47,74.82,91.20,5.20,5.40,4.05]
IMAGES=['ec1440bc5dd57542d48387ca6c752bd4.png','8ceaccb479dfb3363e5f9796d1e5952a.png',
'18027619cce143324078190219d777a8.png','e381ccf45632dad8acbf27a4fa753eea.png','b9cf96b113bc04838a62ba6a283609b8.png']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--image-dir',type=Path);args=ap.parse_args()
    OUT.mkdir(exist_ok=True);items=[];original=args.image_dir
    manifest=json.loads((ROOT/'BMMS_V11_D24_Diagnostics/MANIFEST.json').read_text(encoding='utf-8'))
    hashes={x['file']:x['sha256'] for x in manifest['probes']}
    for (name,times),image in zip(DATA.items(),IMAGES):
        dst=OUT/(name+'.png')
        if not dst.exists():
            assert original is not None,'--image-dir is required only before screenshots are archived'
            shutil.copyfile(original/image,dst)
        if original and (original/image).exists():assert sha(dst)==sha(original/image)
        code=ROOT/'BMMS_V11_D24_Diagnostics'/(name+'.asc');assert sha(code)==hashes[code.name]
        items.append({'probe':name,'screenshot':dst.name,'screenshot_sha256':sha(dst),
            'delivered_source':code.relative_to(ROOT).as_posix(),'delivered_source_sha256':sha(code),
            'association':'user explicitly says images are N01..N05 in order; platform source hash unavailable',
            'pass_count':15,'displayed_error_pct':[0.0]*15,'us':times,'best_column_us':BEST})
    with (OUT/'measurements.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.writer(f);w.writerow(['probe','case','status','displayed_error_pct','time_us','best_column_us'])
        for name,times in DATA.items():
            for i,t in enumerate(times):w.writerow([name,i+1,'Pass','0.00',f'{t:.2f}',f'{BEST[i]:.2f}'])
    report={'date':'2026-09-27','submissions':items,'same_batch_positive_controls':{
        '5':['N03_M_LE32','N04_N_LE32'],'13':['N05_B_EQ1'],'14':['N05_B_EQ1']},
        'working_inference':{'5':{'route':'Native','K':128,'M_values':[16,32],'N_values':[16,32],'B_min':2,'B_max':64,'family':'Dense_SmallK'},
        '13':{'route':'Native','K':128,'M_min':48,'N_min':48,'alignment':16,'B':1,'family':'Dense_SmallK'},
        '14':{'route':'Native','K':128,'M_min':48,'N_min':48,'alignment':16,'B':1,'family':'Dense_SmallK'}},
        'unknown':['exact B for Case5','exact M/N','FP16 versus BF16','TA/TB','hardware profile'],
        'Case6_route':'still unknown; absence of conditional response alone is not a route exclusion',
        'needs_C00_to_decode_current_three_cases':False,'extra_probes_requested':False,
        'performance_candidate':'R25_NATIVE_TARGETED; pending platform verification',
        'noise_scaling_applied':False,'statistical_significance_claimed':False}
    (OUT/'RESULT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (OUT/'AUDIT.md').write_text('''# D24 N01–N05：Native 三点完成第一层定位

用户明确给出图片顺序 N01、N02、N03、N04、N05。每份均 15/15 Pass，误差栏 0.00%。
逐点原始数据见 measurements.csv；图片原字节和对应交付源码 SHA256 见 RESULT.json。
平台没有回传源码 hash，因此“提交对应哪份文件”采用用户明确标注，不声称平台 hash 已核验。

| Probe | Case5 μs | Case13 μs | Case14 μs |
|---|---:|---:|---:|
| N01 K32 | 7.49 | 17.15 | 14.56 |
| N02 K64 | 7.84 | 17.56 | 15.13 |
| N03 M≤32 | 14.67 | 17.51 | 14.96 |
| N04 N≤32 | 14.60 | 17.83 | 15.15 |
| N05 B1 | 7.58 | 98.42 | 43.23 |

同一套源码中，五份 probe 只在不同 predicate 命中时执行完全相同的 Native 单组计划。
Case5 的 N03/N04 是新基线强阳性；Case13/14 的 N05 是强阳性。因此这轮已有逐点校准，
无须再要求 C00。双 K 阴性在该校准下排除 32/64，三点均为 K128。

- Case5：M,N∈{16,32}，2≤B≤64。N03/N04 同时阳性，语义 family 是 Dense_SmallK，
  不能误写成 ShortM 或 ShortN。具体 M、N、B 未知。
- Case13/14：B1，M,N≥48 且 16 对齐，Dense_SmallK。不能据压力倍率确定谁的 M/N 更大。
- 原计划 blocks>1 与强压力响应相符：若 blocks==1，此三点的单组干预不会产生可解释的大幅变化。
  R25 仍把 blocks>1 显式写成保护条件，单核组输入保持原内核。
- Case6 的路由仍未知；当前条件阴性不能排除 Native。

N01/02/05 给 Case5 的未干预观察区间为 7.49–7.84 μs；N01–04 给 Case13 的区间为
17.15–17.83 μs，Case14 为 14.56–15.15 μs。这些是本批观测范围，不是统计置信区间。
不从它们推定候选已加速，不做全局比例去噪，不把最低值拼成一个提交。

最新用户要求直接优化 5/13/14 并验证其他点，本轮据此交付 R25，不继续发 shape probes，
不推进 Case6/7/15 的新优化。R23 保留为已验证基线；R25 的编译、Pass 与性能仍待平台。
''',encoding='utf-8')
    print(json.dumps({'screenshots':len(items),'measurements':75,'all_pass':True,'extra_probes':False}))
if __name__=='__main__':main()

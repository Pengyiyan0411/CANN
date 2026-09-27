"""Keep new screenshots verbatim; R25 attribution is contextual, not explicit."""
from pathlib import Path
import argparse,csv,hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'V11_results/2026-09-27_r25_observed'
DATA=[
 [2.58,5.52,5.17,6.56,6.60,14.67,11.11,93.58,71.01,84.82,101.80,124.60,16.80,13.84,15.30],
 [2.60,5.70,5.04,6.52,6.45,15.02,11.13,92.27,70.50,85.23,101.92,124.60,16.91,13.63,15.03]]
BEST=[1.22,1.58,2.16,2.92,1.89,7.09,3.70,14.88,51.77,72.47,74.82,91.20,5.20,5.40,4.05]
IMAGES=['4535367d954aa0a3ec1214a0c9b3db10.png','3730cb85ac981cd5131ad85a18959031.png']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--image-dir',type=Path);args=ap.parse_args();OUT.mkdir(exist_ok=True)
    source=ROOT/'BMMS_V11_R25/R25_NATIVE_TARGETED.asc';items=[]
    for index,(image,us) in enumerate(zip(IMAGES,DATA),1):
        dst=OUT/f'observation_{index:02d}.png'
        if not dst.exists():
            assert args.image_dir,'First archive requires --image-dir';shutil.copyfile(args.image_dir/image,dst)
        if args.image_dir:assert sha(dst)==sha(args.image_dir/image)
        items.append(dict(observation=index,screenshot=dst.name,screenshot_sha256=sha(dst),pass_count=15,
            displayed_error_pct=[0.0]*15,us=us,best_column_us=BEST))
    with (OUT/'measurements.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.writer(f);w.writerow(['observation','case','status','displayed_error_pct','time_us','best_column_us'])
        for n,us in enumerate(DATA,1):
            for i,t in enumerate(us,1):w.writerow([n,i,'Pass','0.00',f'{t:.2f}',f'{BEST[i-1]:.2f}'])
    result=dict(date='2026-09-27',observations=items,working_source=source.relative_to(ROOT).as_posix(),working_source_sha256=sha(source),
        association='context-inferred R25_NATIVE_TARGETED: latest delivery and user asks to keep Case5 advantage; no filename or platform hash confirmed',
        user_explicit_filename_confirmation=False,platform_source_hash_verified=False,statistical_significance_claimed=False,
        adjacent_R23_control_available=False,performance_policy='freeze Case5; change only Native B1 K128 M,N>32; validate all 15 points before other work')
    (OUT/'RESULT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (OUT/'AUDIT.md').write_text('''# R25 后续两份回传：冻结 Case5，继续优化 13/14

两图均 15/15 Pass，误差栏均显示 0.00%。完整读数在 measurements.csv，原图及 SHA256 在 RESULT.json。
用户没有再标注具体文件名；依据上一轮首选交付和“保持5的优势”，工作归属为 R25_NATIVE_TARGETED。
这不是平台源码 hash 核验，也不能排除用户使用了独立消融版。R26 明确从已归档 R25 完整版生成。

| Case | 图1 μs | 图2 μs | 上轮 N01–N05 中未干预的观察范围 μs |
|---|---:|---:|---:|
| 5 | 6.60 | 6.45 | 7.49–7.84 |
| 13 | 16.80 | 16.91 | 17.15–17.83 |
| 14 | 13.84 | 13.63 | 14.56–15.15 |
| 15 | 15.30 | 15.03 | 15.08–15.54 |

Case5 两次均低于上一批未干预观察范围，按用户要求冻结其特化。
13/14 的下降幅度较小，且缺相邻同环境控制提交，不把这两次差异作为统计显著结论。
其余点未见类似 probe 的倍数级恶化，但仅凭两张图不能证明不存在小幅退化。
不按其他点整体变快/变慢对数据做比例修正，不把各次最低值拼接为一次提交。

下一轮 R26 只修改既有 Native、B=1、K=128、M/N>32、blocks>1 的消费者。
Case5 的多 batch 专用源码、内核绑定、分配和 plan 保持 R25。保留原 R25 作为相邻对照。
平台仍需检查全15点 Pass及耗时；13/14 未出现可重复收益前，不推进其他点。
''',encoding='utf-8')
    print(json.dumps({'screenshots':2,'measurements':30,'all_pass':True,'attribution':'context-inferred R25, not explicitly confirmed'}))
if __name__=='__main__':main()

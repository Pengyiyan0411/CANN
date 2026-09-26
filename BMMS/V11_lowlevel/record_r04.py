"""Preserve the user's SOTA screenshot with explicit contextual R04 attribution."""
from pathlib import Path
import argparse
import csv
import hashlib
import importlib.util
import json
import math
import shutil

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'V11_results/2026-09-26_r04_submission'
TIMES = [2.64,5.58,5.69,6.48,7.25,14.96,10.92,92.45,70.20,108.44,135.29,123.55,18.90,15.28,35.76]
T = [1.22,1.58,2.16,2.92,2.36,7.23,3.70,17.32,51.77,72.47,74.82,91.20,5.21,7.10,9.04]
spec = importlib.util.spec_from_file_location('prior_results', ROOT / 'V11_merge/record_results.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def score(times):
    return sum(100 / (1 + math.log(x/t) / math.log(1.5)) for x, t in zip(times, T)) / 15


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--screenshot', type=Path)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    image = OUT / 'R04_contextual_user_screenshot.png'
    if not image.exists():
        if args.screenshot is None:
            parser.error('--screenshot required on first import')
        shutil.copyfile(args.screenshot, image)
    elif args.screenshot is not None:
        assert sha(image) == sha(args.screenshot)
    source = ROOT / 'BMMS_V11_R04/R04_MACRO_RING_RESIDUAL.asc'
    assert sha(source) == 'f39d584297451a4ef15d559b67879571e3de86e21007f4a02b0b3552a904a09c'
    scores = {name: score(times) for name, times in [('P01_historical', prior.prior.P01),
              ('R01', prior.prior.R01), ('R02', prior.R02), ('R03', prior.R03), ('R04_contextual', TIMES)]}
    rows = [{'case': i+1, 'status': 'Pass', 'displayed_error': '0.00%', 'R04_us': x,
             'R02_us': a, 'R03_us': b, 'T_us': t} for i, (x,a,b,t) in enumerate(zip(TIMES, prior.R02, prior.R03, T))]
    result = {'variant': 'R04_MACRO_RING_RESIDUAL',
              'identity': 'contextual inference: sole immediately preceding candidate R04; user labels result SOTA without repeating filename',
              'explicit_version_label': False, 'platform_source_digest_available': False,
              'local_source_sha256': sha(source), 'screenshot_sha256': sha(image), 'pass_count': 15,
              'case_count': 15, 'ui_error_is_rounded': True, 'T_us': T, 'times_us': TIMES,
              'T9_previous': 51.78, 'T9_current': 51.77, 'scores_same_current_T': scores,
              'rows': rows, 'hidden_shapes_known': False, 'profiler_available': False,
              'next_experiments': ['R05 deferred N reduction', 'R06 full-macro MMAD; independent of R05']}
    (OUT / 'RESULT.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8', newline='\n')
    with (OUT / 'measurements.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    score_table = '\n'.join(f'| {k} | {v:.6f} |' for k,v in scores.items())
    table = '\n'.join(f'| {r["case"]} | {r["R04_us"]:.2f} | {r["R02_us"]:.2f} | {r["R03_us"]:.2f} | {r["T_us"]:.2f} |' for r in rows)
    text = f'''# 本轮SOTA反馈：按上下文归属R04

用户紧接唯一候选R04交付返回截图，标注“SOTA，继续推进”。本记录据上下文归属R04，
并未冒充用户再次明确文件名或取得平台源hash。15/15 Pass，0.00%为界面舍入值。
截图原件和源文件SHA已保存；无hidden shape、profiler、重复计时样本。

## 同口径得分

点9的T再次由51.78变为51.77μs。统一按本轮T及题面公式复算：

| 版本 | 复算分数 |
|---|---:|
{score_table}

本轮比R02增加{scores['R04_contextual']-scores['R02']:.6f}分，
比R01增加{scores['R04_contextual']-scores['R01']:.6f}分，是当前记录中的最好成绩；
“SOTA”来自用户反馈，未查询全赛道排名，不能宣称全榜第一。

| 点 | 本轮/R04 μs | R02 μs | R03 μs | T μs |
|---|---:|---:|---:|---:|
{table}

## 判断

1. 点9–12与R02相差约0.2%–0.4%，点7/15保留R03收益，支持合并两项成功。
   点15从R03的37.08进一步到35.76μs；无重复计时，不把这个小幅变化单独当作稳定优化。
2. 点8仍92.45μs（约5.34倍T），点13约3.63倍T，小点也存在启动/标量/归约开销空间。
   隐藏shape未知，不能从点号直接断定是哪条kernel。
3. 下轮从R04分别派生R05、R06，保持公开路由。R05延后N方向行归约并去掉完整C块的
   无效清填；R06把宏块四条MMAD合为一条，重排L0输入并使用Load2D步长压缩循环。
   两版独立提交以定位效果，暂不组合。目标是降低有源码证据的冗余指令，不先承诺提速。

继续无NPU环境的本地检查及平台提交。极端FP32消去/BF16溢出限制沿用历史边界。
'''
    (OUT / 'AUDIT.md').write_text(text, encoding='utf-8', newline='\n')
    print(json.dumps(scores, indent=2))


if __name__ == '__main__':
    main()

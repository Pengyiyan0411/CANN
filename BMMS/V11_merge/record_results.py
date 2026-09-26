"""Import the two explicitly labelled user screenshots; normalize the changed T9."""
from pathlib import Path
import argparse
import csv
import hashlib
import importlib.util
import json
import math
import shutil

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'V11_results/2026-09-26_r02_r03_submission'
R02 = [2.77,5.52,5.12,6.65,7.36,14.72,13.81,91.60,69.99,108.20,134.84,123.12,18.66,15.40,109.70]
R03 = [2.49,5.27,4.92,6.37,7.03,14.50,10.85,92.20,80.18,120.83,147.89,138.35,18.79,15.06,37.08]
T = [1.22,1.58,2.16,2.92,2.36,7.23,3.70,17.32,51.78,72.47,74.82,91.20,5.21,7.10,9.04]
spec = importlib.util.spec_from_file_location('r01_record', ROOT / 'V11_followup/record_r01.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def item(time, target):
    return 100 / (1 + math.log(time / target) / math.log(1.5))


def score(times):
    return sum(item(x, t) for x, t in zip(times, T)) / len(T)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--r02-screenshot', type=Path)
    parser.add_argument('--r03-screenshot', type=Path)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    records = {}
    for name, times, supplied, filename, digest in [
        ('R02', R02, args.r02_screenshot, 'R02_MACRO_RING.asc', '7e0c3e51e763170973c97d85836b1d217c0746da063352c5e392459a669220e5'),
        ('R03', R03, args.r03_screenshot, 'R03_RESIDUAL_DENSE.asc', '233cb1d95ab788338958f6747a662578c5b1ee0e7e05ba8bef9d26f832c04fac')]:
        image = OUT / (name + '_user_screenshot.png')
        if not image.exists():
            if supplied is None:
                parser.error('--' + name.lower() + '-screenshot required on first import')
            shutil.copyfile(supplied, image)
        elif supplied is not None:
            assert sha(supplied) == sha(image), 'Do not overwrite historical evidence'
        source = ROOT / 'BMMS_V11_R02_R03' / filename
        assert sha(source) == digest
        records[name] = {'identity': 'explicit user label; platform source digest unavailable',
                         'file': source.relative_to(ROOT).as_posix(), 'local_source_sha256': digest,
                         'screenshot_sha256': sha(image), 'pass_count': 15, 'case_count': 15,
                         'displayed_error': '0.00%', 'ui_error_is_rounded': True, 'times_us': times}
    scores = {name: score(times) for name, times in [
        ('P01_historical', prior.P01), ('D01', prior.D01), ('F01', prior.F01),
        ('R01', prior.R01), ('R02', R02), ('R03', R03)]}
    rows = []
    for i, (r01, r02, r03, t) in enumerate(zip(prior.R01, R02, R03, T)):
        rows.append({'case': i + 1, 'R01_us': r01, 'R02_us': r02, 'R03_us': r03, 'T_us': t,
                     'R02_reduction_vs_R01_pct': 100 * (1 - r02 / r01),
                     'R03_reduction_vs_R01_pct': 100 * (1 - r03 / r01),
                     'R02_minus_R01_score_contribution': (item(r02, t) - item(r01, t)) / 15,
                     'R03_minus_R01_score_contribution': (item(r03, t) - item(r01, t)) / 15})
    with (OUT / 'measurements.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    result = {'records': records, 'T_us': T, 'T_change': {'case': 9, 'previous': 52.01, 'current': 51.78},
              'score_formula': 'mean(100/(1+ln(time/T)/ln(1.5)))', 'scores_same_current_T': scores,
              'R01_original_screenshot_T_score': prior.score(prior.R01),
              'R02_minus_R01': scores['R02'] - scores['R01'],
              'R03_minus_R01': scores['R03'] - scores['R01'],
              'rows': rows, 'hidden_shapes_known': False, 'profiler_available': False,
              'paired_repeated_measurements': False,
              'next_action': 'R04 combines R02 with the disjoint R03 branch; no performance claim before submission'}
    (OUT / 'RESULT.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8', newline='\n')
    table = '\n'.join(f'| {r["case"]} | {r["R01_us"]:.2f} | {r["R02_us"]:.2f} | {r["R03_us"]:.2f} | {r["T_us"]:.2f} |' for r in rows)
    score_table = '\n'.join(f'| {name} | {value:.6f} |' for name, value in scores.items())
    report = f'''# R02 / R03 平台反馈审计

用户明确标注图1为R02、图2为R03，均15/15 Pass，界面显示误差0.00%。
源文件、原始截图SHA见RESULT.json；未取得平台源hash、shape或profiler。
显示误差经过舍入，不能推导输出逐位一致。

## 统一得分口径

新截图点9的T为51.78μs，旧截图为52.01μs。下表将所有历史耗时按本轮T重新计算，
不是覆盖历史截图，也不是平台直接返回的总分；公式为题面15点分数均值。

| 版本 | 同本轮T复算分数 |
|---|---:|
{score_table}

R02较R01增加{result['R02_minus_R01']:.6f}分，R03增加{result['R03_minus_R01']:.6f}分。
不同提交无重复测量，几个百分点变化不能直接视为稳定收益。

| 点 | R01 μs | R02 μs | R03 μs | 本轮T μs |
|---|---:|---:|---:|---:|
{table}

## 结论与下一步

1. R02点9–12分别降低{rows[8]['R02_reduction_vs_R01_pct']:.2f}%、
   {rows[9]['R02_reduction_vs_R01_pct']:.2f}%、{rows[10]['R02_reduction_vs_R01_pct']:.2f}%、
   {rows[11]['R02_reduction_vs_R01_pct']:.2f}%；支持保留宏块发布机制。
   点12仍比P01历史108.87μs慢，不能说已经解决所有退化。
2. R03点15从115.13到37.08μs，约{prior.R01[14]/R03[14]:.3f}倍加速；
   点7从13.82到10.85μs。点9–12仍接近R01，符合独立补充分支的预期。
   没有实际路由记录，因此“点15落在残余域”仍是有结果支持的推断。
3. 两版收益集中在不同点，源码上R02域与R03残余域互斥。下一版R04只合并两项，
   不更改tile、核数选择、算术或其他P01分支。实际合并后的成绩需独立提交确认。
4. 点8约92μs、T17.32μs，点13约18.7μs、T5.21μs仍有明显差距；
   后续应围绕公开布局/shape专用路径继续诊断，当前没有证据据此改写这些路径。

不按测试编号选分支，不将逐点最短耗时拼成R04的已测成绩。
已知极端FP32消去/BF16中间溢出限制保留；无测试环境，本轮继续离线检查和平台提交。
'''
    (OUT / 'AUDIT.md').write_text(report, encoding='utf-8', newline='\n')
    print(json.dumps({'scores': scores, 'R02_minus_R01': result['R02_minus_R01'],
                      'R03_minus_R01': result['R03_minus_R01']}, indent=2))


if __name__ == '__main__':
    main()

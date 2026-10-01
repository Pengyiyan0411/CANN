"""Record tested r59-r61 research status without promoting the accepted baseline."""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
V = ROOT/'BMMS_V12'
OUT = ROOT/'V12_npu_lab/results/case12_nmajor_20261001'
data = json.loads((OUT/'SUMMARY.json').read_text(encoding='utf-8'))
report_rel = '../V12_npu_lab/results/case12_nmajor_20261001/REPORT.md'
mainpath = V/'MAINLINE.json'
main = json.loads(mainpath.read_text(encoding='utf-8-sig'))
assert main['accepted_sota']=='v12_baseline_r41.asc'
assert hashlib.sha256((V/main['accepted_sota']).read_bytes()).hexdigest()==main['accepted_sha256']
descriptions = {
    'r59':'N 优先连续 tile 分核，完整 K 的 B 驻留并跨 M 复用，K0=64，双 L0C 和并行行 Max 合并。',
    'r60':'基于 r59，仅将新模块 K0 改为 128；最终版已经修正过宽文本替换并重新完整验证。',
    'r61':'基于 r60，将 L1 内的驻留 B 按六个 K256 NZ 段紧凑排布；不增加 GM 打包。',
}
entries=[]
for ver, result in data['versions'].items():
    path=V/f'v12_{ver}_manifest.json'
    meta=json.loads(path.read_text(encoding='utf-8'))
    assert meta['sha256']==result['sha256']
    meta.update(status='Research only: built and precision passed; mixed performance; not promoted or recommended for Judge15',
                report=report_rel,
                readme=f'v12_{ver}_README.md',
                validation=result,
                remote_evidence_archive_sha256=data['archive']['sha256'])
    path.write_text(json.dumps(meta,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    screen=result['screen']
    readme=f'''# v12_{ver}：Case12 新路径研究版本

**状态：已完成实卡测试；不晋升、不推荐本轮 Judge15 提交。主线仍为 r41。**

{descriptions[ver]}

- [完整源码]({result['file']})，SHA256：`{result['sha256']}`。
- CANN 9 / Ascend910_9362 / 20 Cube 核实际编译通过。
- 精度 164 配置×3次 + 22 配置×5次，共 186 配置/602次，全部通过。
- 8组性能首筛对同批 r41：中位耗时下降 **{screen['median_time_reduction_pct']:.2f}%**（正值更快），最好 {screen['best_time_reduction_pct']:.2f}%，最差 {screen['worst_time_reduction_pct']:.2f}%；4快/4慢，两窗口方向一致。
- 尚未执行独立性能留出、mssanitizer 或 Judge15；以上不是隐藏 Case12 的成绩。
- 删除新增模块和唯一入口 hook 可逐字节恢复 r41，既有内核代码未改。

[完整实验报告、逐形状结果和失败原因]({report_rel})；[版本 manifest](v12_{ver}_manifest.json)。
'''
    (V/f'v12_{ver}_README.md').write_text(readme,encoding='utf-8')
    entries.append(dict(version=f'v12_{ver}',file=result['file'],sha256=result['sha256'],parent='v12_baseline_r41.asc',
                        status=meta['status'],readme=meta['readme'],npu_report=report_rel))
versions={e['version'] for e in entries}
main['candidates']=[e for e in main['candidates'] if e['version'] not in versions]+entries
main.update(latest_experiment_report=report_rel,
            latest_experiment_outcome='r59-r61 implemented and NPU tested; each 186/186 precision configurations passed, 4/8 performance shapes regress. Broad replacement rejected; r41 unchanged.',
            last_implemented_version='v12_r61',active_candidate=None,recommended_candidate=None,
            next_action='Keep r41. Address N128 MTE1/scalar overhead before broad Case12 replacement; any faster subgroup requires frozen guards and independent N/M/dtype performance validation. Existing r58 diagnostic remains pending, not a prerequisite for implementation.')
mainpath.write_text(json.dumps(main,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

# Verify all Markdown evidence links point to local artifacts.
for md in [OUT/'REPORT.md']+[V/f'v12_{ver}_README.md' for ver in data['versions']]:
    for target in re.findall(r'\]\(([^)]+)\)',md.read_text(encoding='utf-8')):
        if '://' not in target:
            assert (md.parent/target.split('#')[0]).exists(), (md,target)

files=[OUT/'REPORT.md',OUT/'SUMMARY.json',OUT/'PERFORMANCE.csv',
       ROOT/'V12_npu_lab/summarize_nmajor.py',Path(__file__),V/'MAINLINE.json']
for ver,result in data['versions'].items():
    files.extend([V/result['file'],V/f'v12_{ver}_README.md',V/f'v12_{ver}_manifest.json',OUT/f'AUDIT_{ver.upper()}.json',
                  ROOT/f'V12_npu_lab/prepare_{ver}.py',OUT/f'{ver}_first8_summary.json'])
record=dict(baseline_sha256=main['accepted_sha256'],archive=data['archive'],
            files={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
(OUT/'LOCAL_MANIFEST.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(dict(accepted=main['accepted_sota'],candidates=[e['version'] for e in entries],
                     report=str(OUT/'REPORT.md'),verified_local_files=len(files)),ensure_ascii=False))

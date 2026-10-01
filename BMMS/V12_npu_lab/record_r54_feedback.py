from pathlib import Path
import hashlib, json, shutil

root = Path(__file__).resolve().parents[1]
v = root / 'BMMS_V12'
out = root / 'V12_results/2026-10-01_r54_feedback'
out.mkdir(exist_ok=True)
src = v / 'v12_r54_case12_stride_gated_m256.asc'
digest = hashlib.sha256(src.read_bytes()).hexdigest()
assert digest == '24d183f027a78e4637c828dc6766aea07626c351053137ec73919ef9fe8cbaaa'
times = [2.48,4.82,5.45,6.45,6.57,14.68,9.52,47.13,66.73,79.44,83.39,115.21,15.10,13.81,11.32]
refs = [1.37,1.83,2.44,3.23,2.33,7.16,3.69,17.32,50.68,68.65,71.25,85.25,5.21,6.08,8.31]
shutil.copyfile(Path(r'E:\Tencent Files\3232896164\nt_qq\nt_data\Pic\2026-10\Ori\923bc3faa7ec45e7aa0225c1508b0655.png'), out / 'judge.png')
data = dict(version='v12_r54', attribution='Inferred from direct reply to r54 delivery; screenshot has no source version/hash label',
    local_source_sha256=digest, independent_runs=1, all_15_pass=True,
    rows=[dict(case=i+1,status='Pass',displayed_error_percent=0,latency_us=t,displayed_reference_us=refs[i]) for i,t in enumerate(times)],
    decision='No clear Case12 gain; keep r41 accepted. r54 coverage is unknown: ordinary timings are not a calibrated MISS.',
    limitations=['Unpaired single Judge run', 'Reference column changed: do not compare normalized scores across runs',
                 'Unchanged latency cannot distinguish full guard rejection from failure of local benefit to transfer'],
    next_step='One complete r54 route-coverage probe, calibrated through the public entry on NPU; no new baseline promotion')
(out/'RESULTS.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
table='\n'.join(f'|{i+1}|{t:.2f}|{refs[i]:.2f}|Pass|' for i,t in enumerate(times))
(out/'REPORT.md').write_text('''# v12_r54 Judge 反馈（2026-10-01）

按直接回复关系归属 r54，截图没有版本/源码哈希标记。15 点全部 Pass、显示误差均 0.00%。

**Case12 为 115.21 μs，没有证明收益，r41 继续作为主线。** 历史 r41 为115.04 μs、保留同一路径的r44为113.68 μs；这些是非配对单次记录，不能据此宣称显著回退。Case11 83.39 μs、Case8 47.13 μs、Case15 11.32 μs，未显示既有结构性收益消失。

r54 本地只在完整资格成立且 N%128==64 的子域有稳定收益。本次普通计时不构成校准过的 MISS，既不能推出 N%128==0，也不能证明 AM256×BN128 已实际执行。新分块整除条件、实际入口核数等仍可拒绝该分支。

下一步用一个 r55 完整入口覆盖探针：沿用 r54 的资格、plan、dtype、pitch、family 和入口顺序，命中后单 Cube 完成真实计算；先在本地校准压力信号。HIT 后才追本地到 Judge 的性能差异；MISS 后沿 r30 覆盖域推进 B/NZ 方案，不直接强开未验证子域。

右侧参考列多点已变化，本文保留原值，不跨截图比较参考归一化得分。

|Case|本次耗时 μs|右侧参考 μs|状态|
|--:|--:|--:|--|
'''+table+'\n',encoding='utf-8')
feedback='../V12_results/2026-10-01_r54_feedback/RESULTS.json'
status='Judge 15/15 Pass; Case12 115.21us, no clear gain. Full route coverage unknown; not promoted.'
main=json.loads((v/'MAINLINE.json').read_text(encoding='utf-8'))
assert main['accepted_sota']=='v12_baseline_r41.asc'
for item in main['candidates']:
    if item['version']=='v12_r54': item.update(status=status,judge_feedback=feedback)
main.update(latest_judge_feedback=feedback,active_candidate=None,next_action='Calibrate and deliver a single complete r54 route-coverage diagnostic; retain r41 baseline')
(v/'MAINLINE.json').write_text(json.dumps(main,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=v/'v12_r54_manifest.json'; meta=json.loads(p.read_text(encoding='utf-8'));meta.update(status=status,judge_feedback=feedback)
p.write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=v/'v12_r54_README.md'; text=p.read_text(encoding='utf-8')
notice='> 2026-10-01 Judge反馈：15/15 Pass；Case12 115.21 μs，无明确收益。r54完整分支是否命中仍未知，主线保留r41。下文为提交前记录。\n\n'
if not text.startswith(notice): p.write_text(notice+text,encoding='utf-8')
print(json.dumps(dict(recorded=str(out),accepted='r41',case12_us=115.21,coverage='unknown')))

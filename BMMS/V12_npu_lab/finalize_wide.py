"""Freeze r62-r64 research evidence while retaining the accepted r41 source."""
from pathlib import Path
import hashlib,json,re
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V12';out=root/'V12_npu_lab/results/case12_wide_load_20261001'
summary=json.loads((out/'SUMMARY.json').read_text(encoding='utf-8'))
report='../V12_npu_lab/results/case12_wide_load_20261001/REPORT.md'
mp=v/'MAINLINE.json';old=mp.read_bytes();main=json.loads(old)
assert main['accepted_sota']=='v12_baseline_r41.asc'
assert hashlib.sha256((v/main['accepted_sota']).read_bytes()).hexdigest()==main['accepted_sha256']
# Preserve the old manifest's historical mainline record as a stable snapshot.
previous=root/'V12_npu_lab/results/case12_nmajor_20261001'
mf=previous/'LOCAL_MANIFEST.json';prior=json.loads(mf.read_text())
if 'BMMS_V12/MAINLINE.json' in prior['files']:
 digest=prior['files']['BMMS_V12/MAINLINE.json']
 assert hashlib.sha256(old).hexdigest()==digest
 snap=previous/'MAINLINE_SNAPSHOT.json';snap.write_bytes(old)
 prior['files'][snap.relative_to(root).as_posix()]=prior['files'].pop('BMMS_V12/MAINLINE.json')
 mf.write_text(json.dumps(prior,indent=2)+'\n')
descriptions={'r62':'保留原分核与宽块，用 dstGap 减少 A 的 L1→L0 装载指令。',
              'r63':'N256 连续 N-major 分核，缓存前 K512 的 B，A256/B128 独立双缓冲。',
              'r64':'r63 的对照：B缓存前 K256，A/B均K256双缓冲，减少阶段切换。'}
entries=[]
for ver,result in summary['versions'].items():
 path=v/f'v12_{ver}_manifest.json';meta=json.loads(path.read_text())
 assert meta['sha256']==result['sha256']
 status='NPU build and precision passed; no material gain; research only' if ver=='r62' else 'NPU build and precision passed; broad performance regresses; research only'
 meta.update(status=status,report=report,validation=result,readme=f'v12_{ver}_README.md',recommended_for_judge15=False)
 path.write_text(json.dumps(meta,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
 screen=result['screen']
 text=f'''# v12_{ver}：Case12 宽块实验

**研究版本，不晋升、不推荐本轮 Judge15；主线仍为 r41。**

{descriptions[ver]}

- [完整源码]({result['file']})；SHA256：`{result['sha256']}`。
- CANN9.0.0 / Ascend910_9362 / 20 Cube 核完整编译通过。
- 164配置×3次 + 22配置×5次，共186配置、602次精度调用，全部通过。
- 同批 r41 的8组性能首筛：中位耗时下降 {screen['median_time_reduction_pct']:.2f}%（正数更快），最好 {screen['best_time_reduction_pct']:.2f}%，最差 {screen['worst_time_reduction_pct']:.2f}%。r62在噪声范围；r63/r64的稳定退化阻止通用替换。
- 没有执行独立性能留出、新的mssanitizer或Judge15；不能把合成样本的收益当作隐藏Case12收益。
- [完整报告、逐项性能及计数器]({report})；[版本manifest](v12_{ver}_manifest.json)。
'''
 (v/f'v12_{ver}_README.md').write_text(text,encoding='utf-8')
 entries.append(dict(version=f'v12_{ver}',file=result['file'],sha256=result['sha256'],parent='v12_baseline_r41.asc',
                     status=status,readme=meta['readme'],npu_report=report))
ids={e['version'] for e in entries};main['candidates']=[e for e in main['candidates'] if e['version'] not in ids]+entries
main.update(latest_experiment_report=report,last_implemented_version='v12_r64',active_candidate=None,recommended_candidate=None,
            latest_experiment_outcome='r62-r64 completed. Each 186 precision configurations/602 calls pass. r62 no material gain; r63/r64 median time reduction -1.73%/-4.17%. r41 remains accepted.',
            next_action='Keep r41. Profiling separates input-bound from compute/pipeline-bound shapes. Retain r63 for a predeclared, independently validated subgroup only; investigate extra merge and A/B event costs separately, without assuming less traffic or fewer instructions guarantees speed.')
mp.write_text(json.dumps(main,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
(out/'MAINLINE_SNAPSHOT.json').write_bytes(mp.read_bytes())
for md in [out/'REPORT.md']+[v/f'v12_{x}_README.md' for x in summary['versions']]:
 for target in re.findall(r'\]\(([^)]+)\)',md.read_text(encoding='utf-8')):
  if '://' not in target:assert (md.parent/target.split('#')[0]).exists(),(md,target)
files=[out/'REPORT.md',out/'SUMMARY.json',out/'PERFORMANCE.csv',out/'PLAN.md',out/'MAINLINE_SNAPSHOT.json',Path(__file__),root/'V12_npu_lab/summarize_wide.py']
for ver,result in summary['versions'].items():
 files.extend([v/result['file'],v/f'v12_{ver}_manifest.json',v/f'v12_{ver}_README.md',out/f'AUDIT_{ver.upper()}.json',root/f'V12_npu_lab/prepare_{ver}.py',out/f'{ver}_first8_summary.json'])
files.extend([root/'V12_npu_lab/audit_r63.py',root/'V12_npu_lab/audit_r64.py'])
(out/'LOCAL_MANIFEST.json').write_text(json.dumps(dict(baseline_sha256=main['accepted_sha256'],archive=summary['archive'],
    files={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}),indent=2)+'\n')
print(json.dumps(dict(accepted=main['accepted_sota'],versions=[e['version'] for e in entries],local_manifest_files=len(files)),ensure_ascii=False))

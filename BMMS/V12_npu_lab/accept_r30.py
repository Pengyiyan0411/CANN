from pathlib import Path
import json
r=Path(__file__).resolve().parents[1];o=r/'BMMS_V12'
p=o/'v12_r30_manifest.json';m=json.loads(p.read_text(encoding='utf-8'));m.update(status='Accepted after user Judge feedback: all15 Pass, Case11 97.09us and Case12 115.12us; original sanitizer limitations remain unresolved',judge_feedback='../V12_results/2026-09-28_r30_feedback/RESULTS.json');p.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(o/'v12_r30_README.md').write_text('''# v12_r30（当前已接受基线）

用户确认有效：15/15 Pass，Case11 97.09μs、Case12 115.12μs，Case8 46.78μs、Case15 11.37μs。两张截图内容相同，只计一次独立测试。

冻结源码为 [v12_baseline_r30.asc](v12_baseline_r30.asc)，r19保留回退。此前本地racecheck/initcheck及冗余同步告警仍未闭环；Judge通过不替代内存同步证明。

[线上数据](../V12_results/2026-09-28_r30_feedback/RESULTS.json) · [原始本地实验报告](../V12_npu_lab/results/dense_pipeline_20260928/REPORT.md)
''',encoding='utf-8')
print('r30 accepted metadata updated; sources unchanged')

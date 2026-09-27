"""Record qualitative feedback and archive the documentation-only R31 checkpoint.

Run after writing the summary and feedback audit. Historical artifacts are verified
against the preceding git manifest; only README and the current audit may change.
This script does not compile, test, alter, or submit a kernel, and does not push git.
"""
from pathlib import Path
import csv
import hashlib
import json
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT / 'CANN_archive'
OUT = REPO / 'BMMS'
PREVIOUS = 'fbd0824d281e5525ea5f2f5ecb41263ff92338e8'
AUDIT = 'BatchMatmulMaxSum_当前审计报告_2026-09-26.md'
SUMMARY = 'BMMS_阶段进度总结_R01-R31_20260927.md'
FEEDBACK = 'V11_results/2026-09-27_r29_r30_r31_feedback'
SNAPSHOT = 'audit_current/AUDIT_R29_R30_R31_DELIVERY.md'
BASELINE = 'BMMS_V11_R25/R25_NATIVE_TARGETED.asc'
BASE_SHA = '7defd06457ddb0e356cbf4cc8407f31cbb7c622acf6efd66070be212fa4eacb2'
CANDIDATES = {
    'R29': ('R29_SHORTK_L1.asc', 'e7451df6ce7bccbc4894a8c021b0f1548acbbb8280da00d485f4440b2c23a2bb', 'no_benefit_reported'),
    'R30': ('R30_NATIVE_M128.asc', '6441027e53c344365c4e4aa7ce57cfb48c32507b633527a5d6ce14d61ab5d331', 'other_cases_regressed_reported'),
    'R31': ('R31_MACRO_K128.asc', '7369fd862ff19e2d3bb3b795a32d9be9ffc772e0fd4f388e8417cea3256e7390', 'other_cases_regressed_reported'),
}
QUOTE = '不行 R29没有收益 R30 R31反而别的点掉了。详细总结一下现在的进度，整理为.md'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(rel):
    return json.loads((ROOT / rel).read_text(encoding='utf-8'))


def write_json(rel, value):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def read_csv(rel):
    with (ROOT / rel).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def cells(line):
    return [s.strip().replace('**', '') for s in line.strip('|').split('|')]


def validate_summary():
    text = (ROOT / SUMMARY).read_text(encoding='utf-8')
    assert '\ufffd' not in text
    section = text.split('## 6. 保留基线的完整平台读数', 1)[1].split('R26/27/28 的重点观察如下', 1)[0]
    rows = [cells(line) for line in section.splitlines() if re.match(r'^\| \d+ \|', line)]
    r23 = read_csv('V11_results/2026-09-27_r23_submission/measurements.csv')
    r25 = read_json('V11_results/2026-09-27_r25_observed/RESULT.json')['observations']
    assert len(rows) == len(r23) == 15
    numeric_checked = 0
    for row, source in zip(rows, r23):
        case = int(row[0])
        assert case == int(source['case'])
        actual = [float(row[1])] + [float(s.strip()) for s in row[2].split('/')] + [float(s.strip()) for s in row[3].split('/')]
        expected = [float(source[k]) for k in ['historical_R14_us', 'R23_run1_us', 'R23_run2_us']]
        expected += [s['us'][case - 1] for s in r25]
        assert actual == expected, (case, actual, expected)
        numeric_checked += 5

    native = read_csv('V11_results/2026-09-27_d24_native/measurements.csv')
    source = {(r['probe'].split('_')[0], int(r['case'])): float(r['time_us']) for r in native}
    for line in text.splitlines():
        if re.match(r'^\| N0[1-5] \|', line):
            row = cells(line)
            assert [float(x) for x in row[2:5]] == [source[(row[0], case)] for case in [5, 13, 14]]
            numeric_checked += 3

    r7 = read_csv('V11_results/2026-09-27_d24_r7/measurements.csv')
    source = {r['probe']: float(r['time_us']) for r in r7 if int(r['case']) == 7}
    for line in text.splitlines():
        if re.match(r'^\| (C01_R03_1G|R7_0[1-5]) \|', line):
            row = cells(line)
            key = next(k for k in source if k == row[0] or k.startswith(row[0] + '_'))
            assert float(row[2]) == source[key]
            numeric_checked += 1

    long_k = read_csv('V11_results/2026-09-27_d24_l00_l05/measurements.csv') + read_csv('V11_results/2026-09-27_d24_l04_l06/measurements.csv')
    source = {r['probe']: float(r['time_us']) for r in long_k if int(r['case']) == 15}
    for line in text.splitlines():
        if re.match(r'^\| L0[0456]_', line):
            row = cells(line)
            assert float(row[2]) == source[row[0]]
            numeric_checked += 1
    assert numeric_checked == 100, numeric_checked
    return numeric_checked


def validate_links(paths):
    count = 0
    for path in paths:
        text = path.read_text(encoding='utf-8')
        assert '\ufffd' not in text, path
        for link in re.findall(r'\]\(([^)]+)\)', text):
            if link.startswith(('http://', 'https://', '#')):
                continue
            target = link.split('#', 1)[0].strip('<>')
            assert (path.parent / target).resolve().exists(), (str(path), target)
            count += 1
    return count


def main():
    raw = subprocess.check_output(['git', 'show', PREVIOUS + ':BMMS/ARCHIVE_MANIFEST.json'], cwd=REPO)
    manifest = json.loads(raw)
    entries = {r['path']: r for r in manifest['files']}
    assert len(entries) == 847
    for rel, row in entries.items():
        if rel in {'README.md', AUDIT}:
            assert sha(OUT / rel) in {row['sha256'], sha(ROOT / rel)}, ('current document out of sync', rel)
        else:
            assert sha(OUT / rel) == row['sha256'], ('archive changed before update', rel)
            assert sha(ROOT / rel) == row['sha256'], ('historical source changed', rel)

    old = subprocess.check_output(['git', 'show', PREVIOUS + ':BMMS/' + AUDIT], cwd=REPO)
    snap = ROOT / SNAPSHOT
    if snap.exists():
        assert snap.read_bytes() == old
    else:
        snap.write_bytes(old)
    assert sha(ROOT / BASELINE) == BASE_SHA
    versions = []
    for version, (filename, digest, status) in CANDIDATES.items():
        rel = 'BMMS_V11_R29_R30_R31/' + filename
        assert sha(ROOT / rel) == digest
        versions.append({
            'version': version, 'source': rel, 'source_sha256': digest,
            'base_source': BASELINE, 'base_source_sha256': BASE_SHA,
            'independent_on_R25': True, 'user_explicit_version_label': True,
            'platform_source_hash_verified': False, 'reported_outcome': status,
            'promoted': False, 'case_timings_us': None,
            'regressed_case_ids': None, 'regression_percent': None,
            'pass_count': None, 'repeat_count': None, 'root_cause_confirmed': False,
        })
    result = {
        'date': '2026-09-27', 'evidence_type': 'user_text_qualitative_feedback',
        'user_text_verbatim': QUOTE, 'screenshots_provided_this_feedback': False,
        'versions': versions, 'retained_baseline': BASELINE, 'retained_baseline_sha256': BASE_SHA,
        'action': 'Do not promote R29/R30/R31; retain full R25; document progress only.',
        'new_kernel_changes': False, 'new_CANN_compile': False, 'new_local_NPU_run': False,
        'quantitative_or_statistical_claims_added': False,
        'prior_delivery_revision': PREVIOUS, 'summary': SUMMARY,
    }
    write_json(FEEDBACK + '/RESULT.json', result)

    old_progress = read_json('V11_results/2026-09-27_d24_l04_l06/PROGRESS.json')
    progress = {
        'date': '2026-09-27', 'current_task': 'Detailed progress summary, documentation only',
        'performance_baseline': BASELINE, 'R25_sha256': BASE_SHA,
        'diagnostic_baseline': 'Frozen original D24 on R23; not R25',
        'completed_submissions': old_progress['completed_submissions'],
        'completed_submission_count': len(old_progress['completed_submissions']),
        'logically_resolved_unrun': old_progress['logically_resolved_unrun'],
        'L_group_resolved': True, 'non_promoted_candidates': ['R26', 'R27', 'R28', 'R29', 'R30', 'R31'],
        'latest_feedback': {v['version']: v['reported_outcome'] for v in versions},
        'next_sequence': [],
        'next_sequence_note': 'No new candidate or probe scheduled by this documentation task; do not rerun unchanged rejected candidates.',
        'optional_case6_route_controls': old_progress['next_case6_sequence'],
        'optional_case6_note': 'Route remains unknown; a null stress response is not sufficient to exclude an already-single-group route.',
        'original_delivery_files_frozen': True,
        'supersedes_current_next_step_from': 'V11_results/2026-09-27_d24_l04_l06/PROGRESS.json',
        'summary': SUMMARY,
    }
    assert progress['completed_submission_count'] == 15
    write_json(FEEDBACK + '/PROGRESS.json', progress)

    (ROOT / 'README.md').write_text('''# BatchMatmulMaxSum：保留 R25，R01–R31 阶段总结

2026-09-27。最新用户反馈：**R29 无收益，R30/R31 导致其他点退化**。三版均不晋升，继续冻结完整 R25；R26/R27/R28 也未晋升。本轮只整理文档和结果，没有修改内核。

- [详细阶段总结：版本演进、逐点证据、探针推导、完整成绩和后续方向](BMMS_阶段进度总结_R01-R31_20260927.md)
- [当前性能源码 R25_NATIVE_TARGETED](BMMS_V11_R25/R25_NATIVE_TARGETED.asc)
- [R29–R31 最新反馈](V11_results/2026-09-27_r29_r30_r31_feedback/AUDIT.md)
- [当前诊断进度](V11_results/2026-09-27_r29_r30_r31_feedback/PROGRESS.json)
- [当前审计](BatchMatmulMaxSum_当前审计报告_2026-09-26.md)
- [原 D24 续跑说明](BMMS_V11_D24_Resume/README.md)

R25 保留 R23 的 Case15 Split-K 和 Case5 的小输出消费策略。D24 仍基于原 R23，已完成 15 个诊断提交；不能把诊断时 Case5 回到约 7 μs 误判为 R25 优势丢失。

R29–R31 此次只有定性反馈，退化点编号、幅度、完整 Pass 数和重复次数未知。历史模型检查不等于硬件收益。原源码、交付包、截图和报告保持原字节；旧文档中的待测建议属于历史快照，以当前总结为准。
''', encoding='utf-8', newline='\n')

    (ROOT / AUDIT).write_text('''# 当前审计：R29 无收益，R30/R31 退化，继续保留 R25

更新日期：2026-09-27。用户反馈本轮无收益及退化，要求详细整理目前进度。本轮为文档工作，没有新增或修改算子。

## 当前决策

| 版本 | 最新结论 | 处理 |
|---|---|---|
| 完整 R25 | 用户要求保留的工作基线 | 原字节冻结，继续用于性能对照 |
| R26/R27 | 13/14 没有建立新收益 | 不合入 |
| R28 | Case15 15.49 μs，尚未建立新收益 | 不合入 |
| R29 | 用户明确无收益 | 不晋升 |
| R30/R31 | 用户明确其他点退化 | 不晋升 |

最新反馈没有提供逐点表、退化点编号、幅度、重复次数或完整 Pass 数；没有替用户填入这些结果。三个候选独立基于 R25，不是累积改动。退化根因未确认，不能把它全部归为波动或指定某一硬件资源。

完整进展见 [R01–R31 阶段总结](BMMS_阶段进度总结_R01-R31_20260927.md)。原文和候选源码摘要绑定见 [最新 RESULT](V11_results/2026-09-27_r29_r30_r31_feedback/RESULT.json)。

## 当前掌握的形状

| Case | 工作结论 |
|---|---|
| 5 | Native，K128；M/N 各为16或32；B>1；Dense_SmallK；保留 R25 小输出策略 |
| 6 | 路线未定位；不能按压力探针无响应排除原本单组的路线 |
| 7 | R03 residual；M16..112/16、N16..240/16、K256..480/32、B<cores；Dense_MidK |
| 13/14 | Native；B1/K128、M/N≥48且16对齐；Dense_SmallK；精确M/N和布局未知 |
| 15 | 当前Split-K；B1、M≤64、N≤128、MN≤4096，K4096..8192/32；空间任务1、原S8或16；SmallOutput_LargeK |

D24 基于原 R23，与性能基线 R25 分开。已实测 N组5个、C01/R7组6个、L组4个，共15个；L01–L03由L05逻辑解决，未单独提交。下一步记录见 [PROGRESS](V11_results/2026-09-27_r29_r30_r31_feedback/PROGRESS.json)。本轮未安排新候选，不再推荐原样重跑已被否定的版本。

## 证据与验证边界

R25 归档两次 Case5 为6.60/6.45 μs，Case15为15.30/15.03 μs；R23 Case15两次均15.18 μs。完整15项对照表在阶段总结中，保留跨轮波动和版本身份限制。

R29–R31 交付时做过CPU源码模型、host分派、资源与故障对照检查；本地没有CANN编译或NPU运行。用户平台性能反馈优先于逻辑指令/搬运计数，不能把模型一致写成保证硬件无退化。历史极端数值限制尚无本轮修复证据。

冻结基线：[R25_NATIVE_TARGETED.asc](BMMS_V11_R25/R25_NATIVE_TARGETED.asc)，SHA-256 `7defd06457ddb0e356cbf4cc8407f31cbb7c622acf6efd66070be212fa4eacb2`。

更新前的审计已按原字节保存在 [R29–R31 交付快照](audit_current/AUDIT_R29_R30_R31_DELIVERY.md)。全部旧源码、ZIP、结果和原图保持冻结，当前结论不回写历史交付文档。
''', encoding='utf-8', newline='\n')

    numeric_checked = validate_summary()
    docs = [ROOT / SUMMARY, ROOT / 'README.md', ROOT / AUDIT, ROOT / FEEDBACK / 'AUDIT.md']
    links = validate_links(docs)
    check = {
        'scope': 'Documentation and archive validation only; not kernel tests',
        'prior_revision': PREVIOUS, 'previous_manifest_entries_checked': 847,
        'historical_artifacts_changed_except_current_readme_and_audit': [],
        'frozen_baseline_sha256': BASE_SHA,
        'summary_sha256': sha(ROOT / SUMMARY),
        'summary_table_numeric_cells_compared_to_original_csv_json': numeric_checked,
        'local_markdown_links_checked': links,
        'completed_diagnostic_submissions': 15,
        'candidate_source_hashes_verified': {v['version']: v['source_sha256'] for v in versions},
        'previous_audit_snapshot_matches_git_blob': snap.read_bytes() == old,
        'new_CANN_compile': False, 'new_local_NPU_run': False,
    }
    write_json(FEEDBACK + '/DOCUMENT_CHECKS.json', check)

    added = [ROOT / SUMMARY, snap, Path(__file__)]
    added += sorted((ROOT / FEEDBACK).glob('*'))
    assert all(p.is_file() for p in added)
    for rel in ['README.md', AUDIT]:
        source = ROOT / rel
        shutil.copyfile(source, OUT / rel)
        entries[rel] = {'path': rel, 'bytes': source.stat().st_size, 'sha256': sha(source)}
    for source in added:
        rel = source.relative_to(ROOT).as_posix()
        assert rel not in entries, rel
        dest = OUT / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        entries[rel] = {'path': rel, 'bytes': source.stat().st_size, 'sha256': sha(source)}
    manifest['scope'] = 'R01-R31 documentation checkpoint: retain frozen R25; explicit user feedback rejects R29 (no benefit) and R30/R31 (other-case regressions); 15 D24 submissions decoded; no new kernel or hardware validation'
    manifest['files'] = [entries[k] for k in sorted(entries)]
    for row in manifest['files']:
        for base in [ROOT, OUT]:
            p = base / row['path']
            assert p.stat().st_size == row['bytes'] and sha(p) == row['sha256'], str(p)
    (OUT / 'ARCHIVE_MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\r\n' if b'\r\n' in raw else '\n')
    readme = (ROOT / 'README.md').read_text(encoding='utf-8')
    (REPO / 'README.md').write_text(re.sub(r'\]\((?!https?://)([^)]+)\)', r'](BMMS/\1)', readme), encoding='utf-8', newline='\n')
    validate_links([REPO / 'README.md'])

    state = read_json('ARCHIVE_STATUS.json')
    state['working_baseline'] = 'Frozen complete R25 retained; R26-R31 not promoted. R29 no benefit; R30/R31 other-case regressions reported by user.'
    state['selected_baseline_reason'] = 'Retain user-accepted Case5 and Split-K gains. No subsequent candidate has met promotion criteria.'
    state['latest_feedback'] = QUOTE
    state['active_work'] = 'Detailed R01-R31 progress summary and qualitative feedback archived; no new kernel changes.'
    state['next_action'] = 'No new candidate scheduled. Retain R25 and completed D24 evidence; use the progress summary for future scoped work.'
    state['current_summary'] = SUMMARY
    state['current_progress_record'] = FEEDBACK + '/PROGRESS.json'
    state['latest_feedback_record'] = FEEDBACK + '/RESULT.json'
    state['documentation_checks'] = FEEDBACK + '/DOCUMENT_CHECKS.json'
    state['archived_source_files_verified'] = len(entries)
    state['previous_847_manifest_entries_frozen_except_current_readme_and_audit'] = True
    state['only_changed_prior_manifest_entries'] = ['README.md', AUDIT]
    state['R29_R30_R31'].update({
        'platform_results_pending': False,
        'qualitative_platform_feedback_received': True,
        'quantitative_platform_timings_available': False,
        'platform_pass_counts_available': False,
        'reported_outcomes': {v['version']: v['reported_outcome'] for v in versions},
        'regressed_case_ids': None, 'root_cause_confirmed': False,
        'promoted': False, 'unchanged_candidates_recommended_for_resubmission': False,
    })
    state['documentation_update_pending_git_commit'] = True
    write_json('ARCHIVE_STATUS.json', state)
    print(json.dumps({'manifest_entries': len(entries), 'new_entries': len(added), 'numerical_cells_verified': numeric_checked, 'local_links_verified': links, 'historical_source_files_changed': 0, 'summary_bytes': (ROOT / SUMMARY).stat().st_size}))


if __name__ == '__main__':
    main()

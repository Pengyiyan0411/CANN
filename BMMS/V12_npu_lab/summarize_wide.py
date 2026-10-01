"""Verify archived NPU evidence and derive r62-r64 decision data."""
from pathlib import Path
import csv
import hashlib
import json
import statistics
import tarfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'V12_npu_lab/results/case12_wide_load_20261001'
ARCHIVE = OUT / 'wide_evidence.tar.gz'
EXPECTED = '7bb74fe6e919ab5b877f3a2ffda04bff5e6dc82fccff2e9573755c8ecbed1b1d'
assert hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() == EXPECTED
EVIDENCE = OUT / 'evidence'
EVIDENCE.mkdir(exist_ok=True)
with tarfile.open(ARCHIVE, 'r:gz') as tf:
    for member in tf.getmembers():
        dest = (EVIDENCE / member.name).resolve()
        assert dest.is_relative_to(EVIDENCE.resolve())
        assert member.isfile(), member.name
    tf.extractall(EVIDENCE, filter='data')
manifest = json.loads((EVIDENCE / 'results/wide_evidence_manifest.json').read_text())
for name, digest in manifest['files'].items():
    assert hashlib.sha256((EVIDENCE / name).read_bytes()).hexdigest() == digest, name

baseline = (ROOT / 'BMMS_V12/v12_baseline_r41.asc').read_bytes()
assert hashlib.sha256(baseline).hexdigest() == '1caf7870ac4154c0f555621ba9c41f4601c6ecee96cb2e8d0bf23acc4fc4f373'
assert baseline == (EVIDENCE / 'r41.asc').read_bytes()
summary = dict(
    baseline='v12_r41', accepted_baseline_unchanged=True,
    scope='Synthetic shapes, not exact hidden Judge Case12 or Judge15',
    measurement='msprof task duration; ABBA two windows/version; 30 calls/window/shape; discard first 5',
    admission_rule='median time reduction >=5%, both windows agree; no unresolved stable regression >3%',
    archive=dict(file=ARCHIVE.name, sha256=EXPECTED, verified_files=len(manifest['files'])),
    versions={},
)
rows = []
for version, filename in [
    ('r62', 'v12_r62_case12_wide_load_gap.asc'),
    ('r63', 'v12_r63_case12_wide_partial_b.asc'),
    ('r64', 'v12_r64_case12_wide_cached_stage.asc'),
]:
    src = (ROOT / 'BMMS_V12' / filename).read_bytes()
    assert src == (EVIDENCE / f'{version}.asc').read_bytes()
    text = src.decode()
    token = '12' + version[1:]
    start = text.index(f'// BMMS{token}_BEGIN')
    marker = f'// BMMS{token}_END\n\n'
    end = text.index(marker, start) + len(marker)
    hook = f'    if(bmms{token}::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
    assert (text[:start] + text[end:]).replace(hook, '', 1).encode() == baseline
    data = json.loads((EVIDENCE / f'results/{version}_first8_summary.json').read_text())
    (OUT / f'{version}_first8_summary.json').write_text(json.dumps(data, indent=2)+'\n')
    gains = []
    stable = True
    for s in data['summary']:
        gain = 100 * (1-s['candidate_median_us']/s['baseline_median_us'])
        gains.append(gain)
        window_gains = [100*(1-b/a) for a,b in zip(s['baseline_medians_us'], s['candidate_medians_us'])]
        stable &= all(g*gain > 0 for g in window_gains)
        cid,B,M,N,K,dt,ta,tb = s['case']
        rows.append(dict(version=version, case=cid,B=B,M=M,N=N,K=K,dtype=dt,ta=ta,tb=tb,
                         baseline_us=s['baseline_median_us'], candidate_us=s['candidate_median_us'],
                         time_reduction_pct=gain, window0_reduction_pct=window_gains[0],
                         window1_reduction_pct=window_gains[1]))
    hit = [r for r in data['runs'] if r['version'] == version]
    assert len(hit) == 16
    assert all(len(r['kernels']) == 1 and f'bmms{token}_' in r['kernels'][0] for r in hit)
    groups = {}
    combined = []
    for kind,count,repeats in [('correctness',164,3), ('extra_precision',22,5)]:
        lines = [json.loads(x) for x in (EVIDENCE/f'results/{version}_{kind}.jsonl').read_text().splitlines()]
        assert len(lines)==count and len({x['case'] for x in lines})==count
        assert all(x['pass'] and x['repeats']==repeats for x in lines)
        assert all(x['cube_cores']==20 for x in lines)
        groups[kind] = dict(configurations=count, calls=count*repeats,
                           max_abs_error=max(x['max_abs_error'] for x in lines),
                           max_tolerance_ratio=max(x['max_tolerance_ratio'] for x in lines))
        combined.extend(lines)
    summary['versions'][version] = dict(
        file=filename,sha256=hashlib.sha256(src).hexdigest(),
        source_reproduces_r41_on_removal=True,build_passed=True,
        precision=groups,all_precision_passed=True,precision_configurations=186,precision_calls=602,
        max_abs_error=max(x['max_abs_error'] for x in combined),
        max_tolerance_ratio=max(x['max_tolerance_ratio'] for x in combined),
        target_hits_verified_on_8_performance_shapes=True,
        screen=dict(shapes=8,faster=sum(g>0 for g in gains),slower=sum(g<0 for g in gains),
                    median_time_reduction_pct=statistics.median(gains),
                    worst_time_reduction_pct=min(gains),best_time_reduction_pct=max(gains),
                    both_windows_same_direction=stable),
        decision='Not admitted for broad Case12 replacement; retain as research only',
        holdout_performance_run=False,mssanitizer_run=False,judge15_run=False,
    )
with (OUT/'PERFORMANCE.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
(OUT/'SUMMARY.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps(summary,indent=2,ensure_ascii=False))

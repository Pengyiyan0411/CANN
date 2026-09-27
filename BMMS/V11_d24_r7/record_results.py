"""Record six explicitly labelled D24 C01/R7 screenshots; no kernel edits."""
from pathlib import Path
import csv
import hashlib
import importlib.util
import io
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'V11_results/2026-09-27_d24_r7'
IMAGES = Path(r'E:\Tencent Files\3232896164\nt_qq\nt_data\Pic\2026-09\Ori')
R25_SHA = '7defd06457ddb0e356cbf4cc8407f31cbb7c622acf6efd66070be212fa4eacb2'
BEST = [1.22,1.58,2.16,2.92,1.89,7.09,3.69,14.88,51.77,72.47,74.82,91.20,5.19,5.40,4.05]
RECORDS = [
    ('C01_R03_1G', '52442f0c1910af1cc60f3a6b8b7c7f82.png', 'positive_control',
     [2.70,5.57,5.15,6.32,7.48,14.67,32.79,93.49,70.10,84.60,100.97,123.97,16.80,14.58,15.52]),
    ('R7_01_M_LT128', '32c74eb0a2faddb0b75538b952726913.png', 'hit',
     [2.66,5.31,5.27,6.41,7.33,14.61,33.58,92.72,70.65,84.34,101.44,124.67,17.04,14.46,15.33]),
    ('R7_02_N_LT256', '9d5aa3f193cd02371636160adc683b82.png', 'hit',
     [2.76,5.47,5.30,6.44,7.03,14.04,33.09,91.31,70.14,84.12,101.07,123.81,16.26,13.86,15.38]),
    ('R7_03_MACRO_OCC_LT_CORES', 'bb6a92f727789e2ed815c692d49e8c96.png', 'hit',
     [2.66,5.18,4.98,6.36,7.43,14.84,34.30,92.23,70.60,84.56,101.45,124.11,16.98,14.42,15.12]),
    ('R7_04_K_GE512', '05877be25a8358414e46d7a154b59110.png', 'miss',
     [2.70,5.50,5.15,6.46,7.48,14.94,11.44,93.01,70.67,84.87,101.65,123.69,17.38,14.74,15.76]),
    ('R7_05_K_GE1024', 'c70a020de19cabbe2b1ec3492c4476f1.png', 'miss',
     [2.64,5.18,5.28,6.45,7.82,15.33,11.45,93.53,71.69,85.39,102.53,123.43,17.66,14.94,15.20]),
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    data = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    if path.exists():
        assert path.read_bytes() == data, f'Existing result differs: {path}'
    else:
        path.write_bytes(data)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location('d24_identity', ROOT / 'V11_diagnostics24/build.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    composition = module.verify()  # Read-only source check, not a CANN build.
    original = ROOT / 'BMMS_V11_D24_Diagnostics'
    manifest = json.loads((original / 'MANIFEST.json').read_text(encoding='utf-8'))
    entries = {x['file']: x for x in manifest['probes'] + manifest['controls']}
    for name, row in entries.items():
        assert sha(original / name) == row['sha256'], name
    resume = ROOT / 'BMMS_V11_D24_Resume'
    resume_manifest = json.loads((resume / 'MANIFEST.json').read_text(encoding='utf-8'))
    for row in resume_manifest['files']:
        assert sha(resume / row['path']) == sha(ROOT / row['original']) == row['sha256']
    assert sha(ROOT / 'BMMS_V11_R25/R25_NATIVE_TARGETED.asc') == R25_SHA
    submissions = []
    for name, filename, decoded, times in RECORDS:
        assert len(times) == len(BEST) == 15 and min(times) > 0
        src = original / (name + '.asc')
        info = entries[src.name]
        assert info['route'] == 'residual'
        dst = OUT / (name + '.png')
        if dst.exists():
            assert sha(dst) == sha(IMAGES / filename)
        else:
            shutil.copyfile(IMAGES / filename, dst)
        submissions.append(dict(
            probe=name, screenshot=dst.name, original_screenshot_filename=filename,
            screenshot_sha256=sha(dst), delivered_source=src.relative_to(ROOT).as_posix(),
            delivered_source_sha256=sha(src), predicate=info['predicate'],
            user_explicit_probe_label=True, platform_source_hash_verified=False,
            pass_count=15, displayed_error_pct=[0.0]*15, us=times, best_column_us=BEST,
            case7_interpretation=decoded))
    decoding = dict(
        route='R03 residual (bmms11d::TryLaunch)', semantic_family='Dense_MidK',
        M_values=list(range(16,128,16)), N_values=list(range(16,256,16)),
        K_values=list(range(256,512,32)), B_relation='1 <= B < cores',
        cores_definition='sanitized run_kernel planner core count; actual value unknown',
        macro_occupancy_expression='B*ceil(M/128)*ceil(N/256)',
        macro_occupancy_simplified='B', exact_B_unknown=True, exact_M_N_K_unknown=True,
        dtype_and_transpose_unknown=True, actual_plan_unknown=True,
        original_mTiles_values=[1,2], original_nTiles_values=[1,2],
        original_tasks_bound='B <= B*pM*pN <= 4*B',
        original_plan_core_limit='blocks = min(cores, tasks)',
        independent_MN_parallelism_proven=False,
        K_upper_bound_evidence='R7_04 negative with strong C01/R7_01..03 single-group controls; R7_05 consistent',
        old_route_bypass_null_inference_rehabilitated=False,
        assumptions=['User probe labels identify the delivered source', 'Same case metadata across submissions'])
    dump(OUT / 'RESULT.json', dict(
        date='2026-09-27', diagnostic_baseline='R23_SPLIT_K',
        performance_baseline_retained='R25_NATIVE_TARGETED',
        submissions=submissions, case7_decoding=decoding,
        case6_route='unknown; C01 null response alone cannot exclude R03',
        case15_note='Earlier Split-K dispatch; R03 probes do not interrogate it',
        statistical_performance_improvement_claimed=False,
        local_CANN_compile=False, local_NPU_run=False, new_device_code=False))
    buf = io.StringIO(newline='')
    writer = csv.writer(buf)
    writer.writerow(['probe','case','status','displayed_error_pct','time_us','best_column_us'])
    for row in submissions:
        for case, us in enumerate(row['us'],1):
            writer.writerow([row['probe'],case,'Pass','0.00',f'{us:.2f}',f'{BEST[case-1]:.2f}'])
    csvpath = OUT / 'measurements.csv'
    payload = buf.getvalue().encode('utf-8')
    if csvpath.exists():
        assert csvpath.read_bytes() == payload
    else:
        csvpath.write_bytes(payload)
    native = json.loads((ROOT / 'V11_results/2026-09-27_d24_native/RESULT.json').read_text(encoding='utf-8'))
    completed = [r['probe'] for r in native['submissions']] + [r['probe'] for r in submissions]
    pending = [Path(name).stem for name in entries if Path(name).stem not in completed]
    dump(OUT / 'PROGRESS.json', dict(
        completed_submissions=completed, next_sequence=['L00_K1_CONTROL','L05_SPATIAL_EQ1'],
        available_without_received_results=pending,
        L05_positive_with_valid_L00='B=1, M<=64, N<=128; skip L01/L02/L03',
        L05_negative_with_valid_L00='Use L01/L02/L03 to decompose the conjunction',
        L00_weak_signal='Do not decode L negatives; use CONTROL_R23 if normal baseline unclear',
        remaining_conditional=['L04_MN_LE4096','L06_SPLITS_GE8','C00_NATIVE_1G','X6_01_MACRO_1G','X6_02_TREE_1W','X6_03_FALLBACK_1CORE'],
        original_delivery_manifests_preserved=True, R25_sha256=R25_SHA))
    dump(OUT / 'IDENTITY_CHECKS.json', dict(
        original_D24_sources_verified=len(entries), original_resume_entries_verified=len(resume_manifest['files']),
        screenshots_verified=6, measurements_recorded=90, R25_sha256=R25_SHA,
        source_composition=composition, local_CANN_compile=False, local_NPU_run=False))
    print(json.dumps({'screenshots':6,'measurements':90,'case7':decoding,'R25_frozen':True}, ensure_ascii=True))


if __name__ == '__main__':
    main()

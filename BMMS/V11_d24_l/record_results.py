"""Archive explicitly labelled D24 L00/L05 observations without kernel changes."""
from pathlib import Path
import csv
import hashlib
import importlib.util
import io
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'V11_results/2026-09-27_d24_l00_l05'
IMAGES = Path(r'E:\Tencent Files\3232896164\nt_qq\nt_data\Pic\2026-09\Ori')
R25_SHA = '7defd06457ddb0e356cbf4cc8407f31cbb7c622acf6efd66070be212fa4eacb2'
RECORDS = [
    ('L00_K1_CONTROL','a061bb3388567b894114895f544f1389.png','positive_control',
     [2.57,5.36,5.29,6.50,7.37,14.46,10.82,92.04,70.38,84.70,101.08,122.93,16.91,14.52,36.78],
     [1.22,1.58,2.16,2.92,1.89,7.09,3.69,14.88,51.64,72.47,74.82,91.20,5.19,5.40,4.05]),
    ('L05_SPATIAL_EQ1','602eee42c443d34025ade848590820da.png','hit',
     [2.75,5.31,5.09,6.35,7.10,14.08,10.57,91.62,70.04,83.91,100.44,124.21,16.46,14.01,37.11],
     [1.22,1.58,2.16,2.92,1.89,7.09,3.69,14.88,51.62,72.47,74.82,91.20,5.19,5.40,4.05]),
]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save(path, data):
    if path.exists():
        assert path.read_bytes() == data, f'Existing evidence differs: {path}'
    else:
        path.write_bytes(data)


def dump(path, value):
    save(path, (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    spec = importlib.util.spec_from_file_location('d24_identity',ROOT/'V11_diagnostics24/build.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    composition = module.verify()
    original = ROOT/'BMMS_V11_D24_Diagnostics'
    manifest = json.loads((original/'MANIFEST.json').read_text(encoding='utf-8'))
    entries = {r['file']:r for r in manifest['probes']+manifest['controls']}
    for name,row in entries.items():
        assert sha(original/name) == row['sha256'], name
    resume = ROOT/'BMMS_V11_D24_Resume'
    resume_manifest = json.loads((resume/'MANIFEST.json').read_text(encoding='utf-8'))
    for row in resume_manifest['files']:
        assert sha(resume/row['path']) == sha(ROOT/row['original']) == row['sha256']
    assert sha(ROOT/'BMMS_V11_R25/R25_NATIVE_TARGETED.asc') == R25_SHA
    submissions = []
    for name,filename,interpretation,times,best in RECORDS:
        assert len(times) == len(best) == 15 and min(times) > 0
        dst = OUT/(name+'.png')
        if dst.exists():
            assert sha(dst) == sha(IMAGES/filename)
        else:
            shutil.copyfile(IMAGES/filename,dst)
        source = original/(name+'.asc')
        submissions.append(dict(probe=name,screenshot=dst.name,original_screenshot_filename=filename,
            screenshot_sha256=sha(dst),delivered_source=source.relative_to(ROOT).as_posix(),
            delivered_source_sha256=sha(source),user_explicit_probe_label=True,
            platform_source_hash_verified=False,pass_count=15,displayed_error_pct=[0.0]*15,
            us=times,best_column_us=best,case15_interpretation=interpretation))
    decoding = dict(route='R23 Split-K (bmms23::TryLaunch)',B=1,
        M_values=[16,32,48,64],N_values=list(range(16,129,16)),
        K_min=4096,K_max=8192,K_alignment=32,original_spatial_tasks=1,
        original_mTiles=1,original_nTiles=1,
        original_R03_plan=dict(pM=1,pN=1,tasks=1,blocks=1),
        original_R23_splits_options=[2,4,8,16],original_R23_blocks_equal_splits=True,
        original_R23_splits_formula='largest power of two <= min(16, cores, floor(K/512))',
        probed_plan=dict(splits=1,blocks=1),
        exact_M_N_K_dtype_transpose_unknown=True,original_split_count_unknown=True,
        MN_le4096_unknown=True,semantic_family_options=['SmallOutput_LargeK','Dense_LargeK'],
        L01_L02_L03_predicates_inferred_true_without_running=True,
        assumptions=['Explicit user labels identify delivered sources','Same case metadata across submissions'])
    dump(OUT/'RESULT.json',dict(date='2026-09-27',diagnostic_baseline='R23_SPLIT_K',
        performance_baseline_retained='R25_NATIVE_TARGETED',submissions=submissions,
        case15_decoding=decoding,case6_route='unknown; no strong L00 response does not exclude Split-K',
        baseline_note='R23 labelled screenshots reported Case15=15.18 us twice; no new adjacent CONTROL_R23 in this pair',
        statistical_performance_improvement_claimed=False,new_device_code=False,
        local_CANN_compile=False,local_NPU_run=False))
    buf = io.StringIO(newline='')
    writer = csv.writer(buf)
    writer.writerow(['probe','case','status','displayed_error_pct','time_us','best_column_us'])
    for row in submissions:
        for case,us in enumerate(row['us'],1):
            writer.writerow([row['probe'],case,'Pass','0.00',f'{us:.2f}',f"{row['best_column_us'][case-1]:.2f}"])
    save(OUT/'measurements.csv',buf.getvalue().encode('utf-8'))
    previous = json.loads((ROOT/'V11_results/2026-09-27_d24_r7/PROGRESS.json').read_text(encoding='utf-8'))
    completed = previous['completed_submissions']+[r['probe'] for r in submissions]
    skipped = {'L01_B_EQ1':'B=1','L02_M_LE64':'M<=64','L03_N_LE128':'N<=128'}
    dump(OUT/'PROGRESS.json',dict(completed_submissions=completed,
        logically_resolved_unrun={k:dict(predicate=v,truth=True,evidence='L05 positive with valid L00 control',submitted=False) for k,v in skipped.items()},
        next_sequence=['L04_MN_LE4096','L06_SPLITS_GE8'],
        next_case6_sequence=['C00_NATIVE_1G','X6_01_MACRO_1G','X6_02_TREE_1W','X6_03_FALLBACK_1CORE'],
        case6_sequence_note='Use complete remaining L screenshots first, then stop route probes after a reliable hit; null response alone does not exclude a route',
        normal_control_if_needed='CONTROL_R23',
        L04_positive='MN<=4096; SmallOutput_LargeK',L04_negative='MN>4096; Dense_LargeK',
        L06_positive='original splits in {8,16}; not necessarily exactly 8',
        L06_negative='original splits in {2,4}; with spatial=1 and K>=4096, cores<8',
        R25_sha256=R25_SHA,original_delivery_files_frozen=True))
    dump(OUT/'IDENTITY_CHECKS.json',dict(original_D24_sources_verified=len(entries),
        original_resume_entries_verified=len(resume_manifest['files']),screenshots_verified=2,
        measurements_recorded=30,R25_sha256=R25_SHA,source_composition=composition,
        new_CANN_compile=False,new_local_NPU_test=False))
    print(json.dumps({'screenshots':2,'measurements':30,'case15':decoding,'R25_frozen':True},ensure_ascii=True))


if __name__ == '__main__':
    main()

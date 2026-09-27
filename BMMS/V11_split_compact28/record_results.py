"""Record user-labelled L04/L06 screenshots and update diagnostic evidence."""
from pathlib import Path
import csv,hashlib,importlib.util,io,json,shutil
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'V11_results/2026-09-27_d24_l04_l06'
IMAGES=Path(r'E:\Tencent Files\3232896164\nt_qq\nt_data\Pic\2026-09\Ori')
R25_SHA='7defd06457ddb0e356cbf4cc8407f31cbb7c622acf6efd66070be212fa4eacb2'
BEST=[1.22,1.58,2.16,2.92,1.89,7.09,3.69,14.88,51.62,72.47,74.82,91.20,5.19,5.40,4.05]
RECORDS=[
 ('L04_MN_LE4096','a92688e9e1610987817f6714ca3d24ef.png',[2.59,5.47,5.19,6.38,7.12,14.45,10.81,91.85,70.25,84.39,101.28,124.30,16.76,14.33,37.05]),
 ('L06_SPLITS_GE8','22910dc85ca10ac5233b759e89baaf36.png',[2.62,5.30,5.08,6.30,7.52,14.73,10.89,92.29,71.69,84.75,101.57,124.15,16.88,14.40,36.87])]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,data):
    if p.exists():assert p.read_bytes()==data,str(p)
    else:p.write_bytes(data)
def dump(p,value):save(p,(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
def main():
    OUT.mkdir(exist_ok=True,parents=True)
    spec=importlib.util.spec_from_file_location('d24_identity',ROOT/'V11_diagnostics24/build.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);composition=module.verify()
    orig=ROOT/'BMMS_V11_D24_Diagnostics';manifest=json.loads((orig/'MANIFEST.json').read_text(encoding='utf-8'))
    entries=manifest['probes']+manifest['controls']
    for row in entries:assert sha(orig/row['file'])==row['sha256']
    resume=ROOT/'BMMS_V11_D24_Resume';rm=json.loads((resume/'MANIFEST.json').read_text(encoding='utf-8'))
    for row in rm['files']:assert sha(resume/row['path'])==sha(ROOT/row['original'])==row['sha256']
    assert sha(ROOT/'BMMS_V11_R25/R25_NATIVE_TARGETED.asc')==R25_SHA
    submissions=[]
    for name,filename,times in RECORDS:
        assert len(times)==15
        p=OUT/(name+'.png');save(p,(IMAGES/filename).read_bytes());source=orig/(name+'.asc')
        submissions.append(dict(probe=name,screenshot=p.name,original_screenshot_filename=filename,
            screenshot_sha256=sha(p),delivered_source=source.relative_to(ROOT).as_posix(),delivered_source_sha256=sha(source),
            user_explicit_probe_label=True,platform_source_hash_verified=False,pass_count=15,displayed_error_pct=[0.0]*15,
            us=times,best_column_us=BEST,case15_interpretation='hit'))
    previous=json.loads((ROOT/'V11_results/2026-09-27_d24_l00_l05/RESULT.json').read_text(encoding='utf-8'))
    d=previous['case15_decoding']
    d.update(MN_le4096=True,MN_le4096_unknown=False,original_R23_splits_options=[8,16],
        semantic_family='SmallOutput_LargeK',semantic_family_options=['SmallOutput_LargeK'],cores_min=8,
        S16_requires='K=8192 and cores>=16; not established that S=16',
        exact_split_count_unknown=True,original_split_count_unknown=True)
    dump(OUT/'RESULT.json',dict(date='2026-09-27',diagnostic_baseline='R23_SPLIT_K',
        performance_baseline_retained='R25_NATIVE_TARGETED',submissions=submissions,case15_decoding=d,
        controls=dict(L00_us=36.78,L05_us=37.11,normal_R23_us=[15.18,15.18]),
        adjacent_normal_control_received=False,case6_route='unknown; a null response does not exclude a route',
        statistical_performance_improvement_claimed=False,local_CANN_compile=False,local_NPU_run=False))
    buf=io.StringIO(newline='');w=csv.writer(buf);w.writerow(['probe','case','status','displayed_error_pct','time_us','best_column_us'])
    for row in submissions:
        for case,t in enumerate(row['us'],1):w.writerow([row['probe'],case,'Pass','0.00',f'{t:.2f}',f'{BEST[case-1]:.2f}'])
    save(OUT/'measurements.csv',buf.getvalue().encode('utf-8'))
    progress=json.loads((ROOT/'V11_results/2026-09-27_d24_l00_l05/PROGRESS.json').read_text(encoding='utf-8'))
    progress['completed_submissions'] += [r['probe'] for r in submissions]
    progress.update(next_sequence=['R28_COMPACT_SPLITK vs frozen CONTROL_R25'],L_group_resolved=True,
        next_case6_sequence_deferred=True,normal_control_if_needed='CONTROL_R25',
        case6_sequence_note='Retained optional diagnostics; not a prerequisite for the user-requested R28 candidate',
        original_delivery_files_frozen=True)
    dump(OUT/'PROGRESS.json',progress)
    dump(OUT/'IDENTITY_CHECKS.json',dict(original_D24_sources_verified=len(entries),original_resume_entries_verified=len(rm['files']),
        source_composition=composition,screenshots_verified=2,measurements_recorded=30,R25_sha256=R25_SHA,
        local_CANN_compile=False,local_NPU_run=False))
    print(json.dumps(dict(measurements=30,case15=d),ensure_ascii=True))
if __name__=='__main__':main()

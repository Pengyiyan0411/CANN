"""Summarize archived evidence; never promote a competition baseline."""
from pathlib import Path
import hashlib
import json
import statistics as st

ROOT=Path(__file__).resolve().parents[1]
dest=ROOT/'V12_npu_lab/results/followup_20260928'
ev=dest/'evidence';rr=ev/'results'
files={
    'r03':['r03_manifest','r03_followup','r03_native','r03_native_holdout'],
    'r07':['r07_original','r07_followup','r07_cases_native','r07_cases_native_holdout'],
    'r08':['r08_original','r08_followup','r08_native'],
    'r09':['r09_cases','r09_cases_followup','r09_cases_native','r09_cases_native_holdout'],
}
summary={}
for ver,names in files.items():
    rows=[json.loads(s) for n in names for s in (rr/f'{n}.jsonl').read_text().splitlines()]
    assert all(r['pass'] for r in rows)
    summary[ver]=dict(cases=len(rows),calls=sum(r['repeats'] for r in rows),
                      max_tolerance_ratio=max(r['max_tolerance_ratio'] for r in rows),
                      max_abs_error=max(r['max_abs_error'] for r in rows))
hashes=json.loads((ev/'logs/followup_hashes.json').read_text())
for v,f in [('r03','v12_baseline_r03.asc'),('r07','v12_r07_paired_ring_consumer.asc'),
            ('r08','v12_r08_native_local_sum.asc'),('r09','v12_r09_native_b_l0_resident.asc')]:
    assert hashlib.sha256((ROOT/'BMMS_V12'/f).read_bytes()).hexdigest()==hashes[f'{v}.asc']

analysis=json.loads((rr/'followup_analysis.json').read_text())
print('Correctness',json.dumps(summary,indent=2))
print('Independent repeat of r07 device stream events:')
for name in ['r07_event_screen_repeat','r07_event_holdout_repeat']:
    for r in analysis[name]:
        print(r['case'],round(r['baseline_us'],3),round(r['candidate_us'],3),round(r['median_paired_reduction_pct'],3))

controls={}
for name in ['r07_controls','r07_controls_repeat']:
    p=rr/f'{name}_summary.json'
    if p.exists():
        controls[name]=json.loads(p.read_text())['summary']
        print(name)
        for r in controls[name]:
            paired=[100*(b/a-1) for a,b in zip(r['baseline_medians_us'],r['candidate_medians_us'])]
            print(r['case'][0],r['baseline_medians_us'],r['candidate_medians_us'],round(st.median(paired),3))
mem={}
for prefix in ['r03_memcheck_control','r07_memcheck']:
    s=(rr/f'{prefix}.log').read_text()
    launcher=(rr/f'{prefix}_launcher.log').read_text()
    mem[prefix]=dict(finished='Sanitizer finished on kernel' in s,
                    output_pass='COMPLETE passed=1' in launcher,
                    ffts_register_warnings=s.count('Warning:Register FFTS_BASE_ADDR'),
                    error_lines=[line for line in s.splitlines() if 'ERROR' in line or '[Error]' in line])
report=dict(correctness=summary,source_binary_hashes=hashes,memcheck=mem,
            r07_independent_events={k:v for k,v in analysis.items() if k.startswith('r07_event')},
            r09_events={k:v for k,v in analysis.items() if k.startswith('r09_event')},
            guard_controls=controls,accepted_baseline='v12_baseline_r03.asc',
            all_inputs_synthetic=True,hidden15_validated=False)
(dest/'SUMMARY.json').write_text(json.dumps(report,indent=2)+'\n')
print('Memcheck',mem)

mainline_path=ROOT/'BMMS_V12/MAINLINE.json'
mainline=json.loads(mainline_path.read_text())
new_candidates=[]
for ver,name,count,status in [
    ('r07','v12_r07_paired_ring_consumer.asc',182,'retained candidate; two fresh-process event comparisons positive by about 0.4-2.1% on nine synthetic shapes; hidden15 not tested; no promotion'),
    ('r08','v12_r08_native_local_sum.asc',141,'rejected for promotion; synthetic performance mixed/no stable benefit'),
    ('r09','v12_r09_native_b_l0_resident.asc',182,'rejected for promotion; device-event effect within noise on screen and holdout'),
]:
    manifest_path=ROOT/f'BMMS_V12/v12_{ver}_manifest.json'
    manifest=json.loads(manifest_path.read_text())
    manifest.update(CANN_compiled=True,NPU_tested=True,synthetic_precision_cases=count,
                    repeats_per_case=3,competition_hidden15_tested=False,status=status,
                    npu_report='../V12_npu_lab/results/followup_20260928/REPORT.md')
    manifest['scope']='Host checks plus actual device build/correctness; performance scope and limits in npu_report.'
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    new_candidates.append(dict(version=f'v12_{ver}',file=name,sha256=hashes[f'{ver}.asc'],
                               parent='v12_baseline_r03.asc',status=status,
                               npu_report='../V12_npu_lab/results/followup_20260928/REPORT.md'))
mainline['candidates']=[c for c in mainline['candidates'] if c['version'] not in {'v12_r07','v12_r08','v12_r09'}]+new_candidates
mainline['naming']='v12_rxx; r03 accepted; r06 no clear gain; r07 retained synthetic candidate; r08/r09 not promoted'
mainline['next_action']='Keep r03 accepted. r07 requires hidden15 coverage/performance confirmation; do not repeat r08/r09 hypotheses. Next local direction: profile Split-K long-K merge/fixed overhead on synthetic cluster.'
mainline_path.write_text(json.dumps(mainline,indent=2)+'\n')

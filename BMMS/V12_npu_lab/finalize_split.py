"""Bind local deliverables to archived device evidence; keep r03 accepted."""
from pathlib import Path
import hashlib,json,statistics as st
ROOT=Path(__file__).resolve().parents[1]
dest=ROOT/'V12_npu_lab/results/split_20260928';ev=dest/'evidence';rr=ev/'results'
hashes=json.loads((ev/'logs/split_hashes.json').read_text())
analysis=json.loads((rr/'split_analysis.json').read_text())
files={'r03':'v12_baseline_r03.asc','r10':'v12_r10_splitk_full_shard.asc',
       'r11':'v12_r11_splitk_parallel_merge.asc','r12':'v12_r12_splitk_adaptive_merge.asc'}
for v,f in files.items():assert hashlib.sha256((ROOT/'BMMS_V12'/f).read_bytes()).hexdigest()==hashes[v+'.asc']
precision={}
for v in files:
    names=[f'split_{v}_precision']+([] if v=='r03' else [f'split_{v}_legacy34',f'split_{v}_legacy66'])
    if v in ['r03','r12']:names.append(f'split_{v}_controls10')
    rows=[json.loads(s) for name in names for s in (rr/(name+'.jsonl')).read_text().splitlines()]
    assert all(r['pass'] for r in rows)
    precision[v]=dict(cases=len(rows),calls=sum(r['repeats'] for r in rows),
                      max_tolerance_ratio=max(r['max_tolerance_ratio'] for r in rows),
                      max_abs_error=max(r['max_abs_error'] for r in rows))
events={}
for name,rows in analysis.items():
    if not name.startswith('split_'):continue
    gains=[r['paired_gain_pct'] for r in rows]
    events[name]=dict(cases=len(rows),gain_pct_min=min(gains),gain_pct_median=st.median(gains),
                      gain_pct_max=max(gains),negative_cases=[r for r in rows if r['paired_gain_pct']<0])
guards={v:json.loads((rr/f'split_{v}_guard_summary.json').read_text())['summary'] for v in ['r10','r11','r12']}
for tag in ['split_r12_routes','split_r12_routes_repeat','split_r12_dot_control']:
    p=rr/f'{tag}_summary.json'
    if p.exists():guards[tag]=json.loads(p.read_text())['summary']
sanitizers={}
for tool in ['memcheck','racecheck']:
    p=rr/f'split_r12_{tool}.log';lp=rr/f'split_r12_{tool}_launcher.log'
    s=p.read_text(errors='replace') if p.exists() else '';launch=lp.read_text(errors='replace') if lp.exists() else ''
    sanitizers[tool]=dict(skipped=('temporarily ignored' in s or 'No active sanitizer' in s),finished='Sanitizer finished on kernel' in s,outputs_passed='COMPLETE passed=2' in launch,
                         ffts_warnings=s.count('Warning:Register FFTS_BASE_ADDR'),
                         errors=[line for line in (s+'\n'+launch).splitlines() if 'ERROR' in line or '[Error]' in line])
report=dict(accepted_baseline='v12_baseline_r03.asc',recommended_candidate=files['r12'],
            all_inputs_synthetic=True,competition_hidden15_tested=False,precision=precision,
            event_summary=events,guard_controls=guards,sanitizers=sanitizers,source_binary_hashes=hashes)
(dest/'SUMMARY.json').write_text(json.dumps(report,indent=2)+'\n')
state=ROOT/'BMMS_V12/MAINLINE.json';main=json.loads(state.read_text())
status={'r10':'not selected: mixed gains and repeatable regressions on the synthetic Split-K cluster',
        'r11':'strong independent epilogue candidate; retained as structural control; r12 evaluated as combined candidate',
        'r12':'recommended for full Judge test after local validation; synthetic results only; r03 still accepted'}
main['candidates']=[c for c in main['candidates'] if c['version'] not in {'v12_r10','v12_r11','v12_r12'}]
for v in ['r10','r11','r12']:
    mp=ROOT/f'BMMS_V12/v12_{v}_manifest.json';m=json.loads(mp.read_text())
    m.update(CANN_compiled=True,NPU_tested=True,synthetic_precision_cases=precision[v]['cases'],repeats_per_case=3,
             competition_hidden15_tested=False,status=status[v],npu_report='../V12_npu_lab/results/split_20260928/REPORT.md')
    m['scope']='Narrow Case15 metadata guard; actual build and synthetic correctness/performance recorded in npu_report.'
    mp.write_text(json.dumps(m,indent=2)+'\n')
    main['candidates'].append(dict(version='v12_'+v,file=files[v],sha256=hashes[v+'.asc'],parent=files['r03'],
                                   status=status[v],npu_report=m['npu_report']))
main['naming']='v12_rxx; r03 accepted; r07 actual gain within noise; r12 Case15 candidate pending Judge'
main['next_action']='Full15 Judge comparison r03/r12; next local direction Case8 phase attribution, then one structural experiment. See NEXT_DIRECTIONS.md.'
state.write_text(json.dumps(main,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(precision=precision,event_summary=events,sanitizers=sanitizers),indent=2))

from pathlib import Path
import json,hashlib,zipfile
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V12';out=root/'V12_npu_lab/results/r39_20260929'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
summary=read(out/'evidence/results/r39_summary.json');assert summary['all_pass'] and summary['precision_calls']==498
source=v/'v12_r39_probe_r37_plan_change.asc';digest=hashlib.sha256(source.read_bytes()).hexdigest()
manifest=read(v/'v12_r39_manifest.json');assert manifest['sha256']==digest
manifest.update(status='NPU full build and 166x3 precision passed; 8 HIT/10 MISS profiler calibration passed; ready for Judge diagnostic only',
    report='../V12_npu_lab/results/r39_20260929/REPORT.md',precision_configurations=166,precision_calls=498,
    hit_calibration_ratio_range=summary['hit_ratio_range'],miss_calibration_ratio_range=summary['miss_ratio_range'])
(v/'v12_r39_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
main=read(v/'MAINLINE.json');assert main['accepted_sota']=='v12_baseline_r33.asc'
old=main.get('active_diagnostic')
if old and old.get('version')!='v12_r39' and not any(x['version']==old['version'] for x in main['historical_diagnostics']):
 old['historical']=True;main['historical_diagnostics'].append(old)
main['active_diagnostic']=dict(version='v12_r39',file=source.name,sha256=digest,parent='v12_baseline_r33.asc',
 purpose='full r37 route guards and actual plan change; single-group real computation only on HIT',status=manifest['status'],readme='v12_r39_README.md',historical=False)
main['next_action']='Submit diagnostic r39; judge11/12 independently for strong slowdown. If no HIT, inspect route/unchanged plan; if HIT, revisit real-plan performance. r33 remains accepted; r37 not promoted.'
main['latest_experiment_report']='../V12_npu_lab/results/r39_20260929/REPORT.md'
(v/'MAINLINE.json').write_text(json.dumps(main,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(out/'SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
with zipfile.ZipFile(v/'v12_r39_submission.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in [source,v/'v12_r39_README.md',v/'v12_r39_manifest.json']:z.write(p,p.name)
with zipfile.ZipFile(v/'v12_r39_submission.zip') as z:assert z.testzip() is None
assert hashlib.sha256((v/'v12_baseline_r33.asc').read_bytes()).hexdigest()=='86debd5c403af4bb436d6c042de4530faf05637cf6fd1aeaae6ed6b410d11d80'
print('r39 ready; r33 baseline hash unchanged; no performance candidate promoted')

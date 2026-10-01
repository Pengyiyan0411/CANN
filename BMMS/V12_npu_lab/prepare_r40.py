from pathlib import Path
import json,hashlib,shutil
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V12';lab=root/'V12_npu_lab/narrow_dense'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
old=(v/'v12_r39_probe_r37_plan_change.asc').read_bytes().decode()
guard='''    if((dtype!=1&&dtype!=2)||!bmms1230::Eligible(B,M,N,K,cores)||
       !bmms1230::AlignedPitch(M,N,K,ta,tb))return false;'''
newguard='''    if((dtype!=1&&dtype!=2)||!bmms1230::Eligible(B,M,N,K,cores)||
       !bmms1230::AlignedPitch(M,N,K,ta,tb)||cores<2||
       !bmms1237::InDomain(B,M,N,K))return false;'''
comparison='return old.pM!=next.pM||old.pN!=next.pN||old.tasks!=next.tasks||old.blocks!=next.blocks;'
newcomparison='return old.pM==next.pM&&old.pN==next.pN&&old.tasks==next.tasks&&old.blocks==next.blocks;'
a=old.index('// BMMS1239_BEGIN');b=old.index('// BMMS1239_END',a)+len('// BMMS1239_END')
mod=old[a:b];assert mod.count(guard)==1 and mod.count(comparison)==1
changed=mod.replace(guard,newguard).replace(comparison,newcomparison).replace('1239','1240')
s=old[:a]+changed+old[b:];s=s.replace('if(bmms1239::TryLaunch','if(bmms1240::TryLaunch')
recovered=s.replace(changed,mod,1).replace('if(bmms1240::TryLaunch','if(bmms1239::TryLaunch')
assert recovered==old
name='v12_r40_probe_r37_unchanged_in_domain.asc';(v/name).write_bytes(s.encode());(lab/'r40.asc').write_bytes(s.encode())
main=(lab/'main_r39.asc').read_text(encoding='utf-8').replace('bmms1239','bmms1240').replace('r39_hit','r40_hit')
(lab/'main_r40.asc').write_text(main,encoding='utf-8')
cm=(lab/'CMakeLists.txt').read_text(encoding='utf-8')
block=cm[cm.index('add_executable(bench_r39'):].replace('r39','r40')
assert 'bench_r40' not in cm
(lab/'CMakeLists.txt').write_text(cm+'\n'+block,encoding='utf-8')
manifest=dict(version='v12_r40',kind='diagnostic only; intentionally slower on predicate HIT',parent='v12_baseline_r33.asc',construction_parent='v12_r39_probe_r37_plan_change.asc',sha256=hashlib.sha256(s.encode()).hexdigest(),
 predicate='r30 full route guards AND cores>=2 AND r37 InDomain AND old/new plans identical',new_device_entries=0,source_byte_recovery_to_r39=True,status='pending NPU calibration')
write(v/'v12_r40_manifest.json',manifest);print(json.dumps(manifest))

feedback=root/'V12_results/2026-09-29_r39_feedback';feedback.mkdir(exist_ok=True)
img=Path(r'E:\Tencent Files\3232896164\nt_qq\nt_data\Pic\2026-09\Ori\abf241b195707412edb4a34c6afe5fb5.png')
if img.exists():shutil.copyfile(img,feedback/'judge_r39.png')
values=[2.33,4.34,5.16,6.45,6.60,14.94,9.59,45.88,65.45,79.29,97.35,114.93,15.28,13.95,11.50]
prior=read(root/'V12_results/2026-09-28_r33_feedback/RESULTS.json')
rows=[dict(case=r['case'],status='Pass',displayed_error_percent=0.0,latency_us=t,platform_best_us=r['platform_best_us'],r33_us=r['latency_us']) for r,t in zip(prior['rows'],values)]
write(feedback/'RESULTS.json',dict(version='v12_r39',version_attribution='Inferred from direct response to r39 delivery; screenshot has no version/hash label',source='user screenshot',source_sha256=hashlib.sha256(old.encode()).hexdigest(),source_hash_visible_in_screenshot=False,
 independent_runs=1,all_15_pass=True,screenshot_copied=img.exists(),rows=rows,decision='Both11/12 show no stress response, supporting predicate FALSE: no actual r37 plan switch. Does not distinguish failed optimization guards from unchanged plan inside domain. Keep r33 and calibrate complementary in-domain unchanged-plan r40.'))
mainline=read(v/'MAINLINE.json');assert mainline['accepted_sota']=='v12_baseline_r33.asc'
d=mainline['active_diagnostic'];assert d['version']=='v12_r39'
d.update(status='Judge all15 Pass;11=97.35us,12=114.93us: neither shows stress signal; predicate FALSE supported',historical=True,feedback='../V12_results/2026-09-29_r39_feedback/RESULTS.json')
mainline['latest_judge_feedback']=d['feedback'];mainline['next_action']='Calibrate r40 then test whether unchanged plans are inside the complete r37 optimization domain; keep r33.'
write(v/'MAINLINE.json',mainline)
m=read(v/'v12_r39_manifest.json');m.update(status=d['status'],judge_feedback=d['feedback']);write(v/'v12_r39_manifest.json',m)
for p in [v/'v12_r39_README.md',root/'V12_npu_lab/results/r39_20260929/REPORT.md']:
 text=p.read_text(encoding='utf-8')
 prefix='> Judge更新：r39全15点Pass，11/12=97.35/114.93μs，均无压力信号，支持未切换计划；主线仍为r33。以下保留提交前校准记录。\n\n'
 if not text.startswith('> Judge更新：'):p.write_text(prefix+text,encoding='utf-8')

# Reuse verified probe pipeline with fresh run identifiers and representative HIT/MISS samples.
script=(lab/'check_r39.sh').read_text(encoding='utf-8').replace('r39','r40').replace('R39','R40')
script=script.replace('ids={0,5,6,9,12,19,21,22,34,35,46,54,58,74,93,95,99,101}',
 'ids={0,5,6,9,12,19,21,22,34,35,46,50,54,58,66,70,74,93,95,99,101}')
(lab/'check_r40.sh').write_bytes(script.encode('utf-8'))
archive=(lab/'archive_r39.py').read_text(encoding='utf-8').replace('r39','r40')
(lab/'archive_r40.py').write_text(archive,encoding='utf-8')

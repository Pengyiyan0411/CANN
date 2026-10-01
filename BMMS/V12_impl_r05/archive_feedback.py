from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'BMMS_V12'
D=ROOT/'V12_results/2026-09-28_r05_coverage';D.mkdir(parents=True,exist_ok=True)
source=Path('E:/Tencent Files/3232896164/nt_qq/nt_data/Pic/2026-09/Ori/54d3db190bccb1e35590fb9518562260.png')
copied=source.exists()
if copied:shutil.copyfile(source,D/'r05_result.png')
times=[2.16,4.59,5.13,6.32,6.54,14.14,8.99,62.37,765.68,83.83,100.60,122.54,14.47,13.36,15.23]
best=[1.22,1.58,2.13,2.92,1.89,7.07,3.68,14.88,50.68,72.39,74.82,91.20,5.14,5.40,4.05]
sha=hashlib.sha256((OUT/'v12_r05_probe_r04_coverage.asc').read_bytes()).hexdigest()
assert sha=='485147ab95fe70dfed37f8a2848ecb95d5e7d2646cc44e54ce9a6ca3abf0056b'
data={'version':'v12_r05','version_attribution':'inferred from immediate preceding request to submit r05; screenshot itself has no version label','source':'user screenshot','screenshot_path_supplied':str(source),'screenshot_copied':copied,'local_candidate_sha256':sha,'source_hash_visible_in_screenshot':False,'all_15_pass':True,'all_displayed_error_percent':0.0,'rows':[{'case':i+1,'status':'Pass','displayed_error_percent':0.0,'latency_us':t,'platform_best_us':best[i]} for i,t in enumerate(times)],'case9':{'decision':'strong positive for full r04/r02 dispatch predicate','new_evidence':['B=1','M,N>=1024 and16-aligned','1024<=K<1536 and32-aligned','floor(original nTiles/pN)>=2'],'not_proven':['exact shape','actual cores/grid','memory bottleneck','r04 performance']},'case10':{'decision':'no stress response; supports full predicate false given previous reported same-route strong calibration','remaining_alternatives_under_prior_MNK_evidence':['B!=1','floor(original nTiles/pN)<2'],'limits':'no same-run unconditional positive control; do not identify which predicate failed'},'next_action':'test existing r04 against accepted r03 for Case9; no new Case9 shape probe; retain complete15-case results','baseline':'v12_r03'}
(D/'RESULTS.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=OUT/'MAINLINE.json';s=json.loads(p.read_text(encoding='utf-8'))
s['active_diagnostic']['status']='user screenshot 15/15 Pass; Case9 strong HIT765.68us; Case10 no stress83.83us, supports NO'
s['active_diagnostic']['feedback']='../V12_results/2026-09-28_r05_coverage/RESULTS.json'
s['review']['latest_evidence']='r05 resolves Case9 full-guard coverage; Case10 supports non-coverage; performance bottleneck remains unproven'
s['candidates'][0]['status']='Case9 coverage confirmed by r05; local checks passed; r04 device compilation and performance evaluation still pending'
s['next_action']='Evaluate existing r04 on Case9 while checking r03 Case2 and all other points; no new kernel generated'
p.write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'archived':str(D),'screenshot_copied':copied,'baseline_unchanged':s['accepted_sota']},ensure_ascii=False))

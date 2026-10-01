import hashlib,json,shutil,collections,re
import build as b
raw=b.BASE.read_bytes();assert hashlib.sha256(raw).hexdigest()==b.SHA
candidate=b.OUT/(b.NAME+'.asc');data=candidate.read_bytes();digest=hashlib.sha256(data).hexdigest()
mod=b.module(raw.decode().replace('\r\n','\n')).encode()
hook=b'    if(bmms1206::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\r\n'
assert data.count(mod)==data.count(hook)==1
assert data.replace(mod,b'',1).replace(hook,b'',1)==raw
assert b'BMMS1204_BEGIN' not in data and b'BMMS1202_BEGIN' not in data
for name in ['v12_r06_cpu_checks.json','v12_r06_host_checks.json','v12_r06_manifest.json']:
    report=json.loads((b.OUT/name).read_text());assert report.get('source_sha256',report.get('sha256'))==digest
assert (b.H/'extracted.hpp').read_text()==(b.H/'cpu_build/extracted.hpp').read_text()
assert (b.OUT/'v12_r03_case2_static_k.asc').read_bytes()==raw
assert hashlib.sha256((b.OUT/'V12_BASELINE_R52.asc').read_bytes()).hexdigest()=='3c66689f4a38b4b6b02aa92547b39065a55d3fdfbcf767d6a53a4618f34cc284'
assert hashlib.sha256((b.OUT/'v12_r04_case9_10_partial_a_cache.asc').read_bytes()).hexdigest()=='d4c0e539ca2145aa520e7b63c7a6bd8b9006ef3d54fa531971b1cf4c67720605'
b.write(b.OUT/'v12_r06_audit.json',json.dumps({'candidate_sha256':digest,'parent_sha256':b.SHA,'r03_recovered_byte_for_byte':True,'baseline_files_unchanged':True,'device_consumer_and_original_planner_unchanged':True,'test_hashes_match':True,'fault_injection_restored':True,'CANN_compiled':False,'NPU_tested':False},indent=2)+'\n')
D=b.ROOT/'V12_results/2026-09-28_r04_feedback';D.mkdir(exist_ok=True,parents=True)
image=b.ROOT.parent/'unused';image=__import__('pathlib').Path('E:/Tencent Files/3232896164/nt_qq/nt_data/Pic/2026-09/Ori/7a884781f5e60328d31d50083629c7c6.png')
copied=image.exists()
if copied:shutil.copyfile(image,D/'r04_result.png')
times=[2.28,4.94,5.29,6.34,6.40,14.29,8.95,62.32,69.09,83.57,100.61,122.10,14.46,13.17,15.12]
best=[1.22,1.58,2.13,2.92,1.89,7.07,3.68,14.88,50.68,72.39,74.82,91.20,5.14,5.40,4.05]
b.write(D/'RESULTS.json',json.dumps({'version':'v12_r04','version_attribution':'immediate preceding request to submit r04; image has no source/version hash','all_15_pass':True,'all_displayed_error_percent':0.0,'screenshot_copied':copied,'rows':[{'case':i+1,'latency_us':t,'platform_best_us':best[i]} for i,t in enumerate(times)],'user_assessment':'optimization not obvious; requests a more aggressive design','decision':'not promoted; keep accepted r03; r05 had confirmed Case9 guard hit, so lack of meaningful benefit is not explained by missed dispatch','same_run_r03_control_available':False},ensure_ascii=False,indent=2)+'\n')
p=b.OUT/'MAINLINE.json';s=json.loads(p.read_text(encoding='utf-8'))
if not any(x['version']=='v12_r04' for x in s['historical_candidates']):s['historical_candidates'].append({'version':'v12_r04','file':'v12_r04_case9_10_partial_a_cache.asc','status':'user screenshot15Pass; Case9 69.09us; no meaningful gain; not promoted','feedback':'../V12_results/2026-09-28_r04_feedback/RESULTS.json'})
s['candidates']=[{'version':'v12_r06','file':candidate.name,'sha256':digest,'parent':b.BASE.name,'status':'structural macro-MMAD candidate; CPU and host checks passed; CANN/NPU pending'}]
s['next_action']='Submit r06; compare Case9 to normal r03 behavior and check all15points; r03 remains accepted SOTA'
s['naming']='v12_rxx; r03 accepted; r04 no meaningful gain; r05 diagnostic completed; r06 pending'
b.write(p,json.dumps(s,ensure_ascii=False,indent=2)+'\n');print('r04 feedback archived; r06 audited; r03 unchanged.')

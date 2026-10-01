import json,hashlib,re,collections
import build as b
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
raw=b.BASE.read_bytes();assert sha(b.BASE)==b.SHA
frozen=b.OUT/'v12_baseline_r03.asc'
if frozen.exists():assert frozen.read_bytes()==raw
else:frozen.write_bytes(raw)
manifest=json.loads((b.OUT/'v12_r04_manifest.json').read_text())
candidate=b.OUT/(b.NAME+'.asc');data=candidate.read_bytes()
src=raw.decode().replace('\r\n','\n');mod=b.module(src)
hook=b'    if(bmms1204::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\r\n'
assert data.count(mod.encode())==data.count(hook)==1
assert data.replace(mod.encode(),b'',1).replace(hook,b'',1)==raw
assert b'BMMS1202_BEGIN' not in data
for file in ['v12_r04_cpu_checks.json','v12_r04_host_checks.json']:
    assert json.loads((b.OUT/file).read_text())['source_sha256']==sha(candidate)==manifest['sha256']
assert (b.H/'extracted.hpp').read_text()==(b.H/'cpu_build/extracted.hpp').read_text()
old=src[src.index('template<class T,bool TA,bool TB>\nclass ReuseProducer'):src.index('class RowMaxConsumer')]
new=mod[mod.index('template<class T,bool TA,bool TB>\nclass CachedAProducer'):mod.index('} // namespace bmms1204')]
pat=r'AscendC::(?:SetFlag|WaitFlag|AllocEventID|CrossCoreWaitFlag|CrossCoreSetFlag)[^;]+;'
# Static event callsites are identical; runtime counts also depend on loop bounds.
assert collections.Counter(re.findall(pat,old))==collections.Counter(re.findall(pat,new))
assert sha(b.OUT/'V12_BASELINE_R52.asc')=='3c66689f4a38b4b6b02aa92547b39065a55d3fdfbcf767d6a53a4618f34cc284'
assert sha(b.ROOT/'V11_analysis_r43/R43_CASE8_PADDED_MACRO.asc')=='15e2c9a0f73e7534c26400107389dcd8e5cf685b5f6f477c7a3684ad3991df2d'
feedback={'date':'2026-09-28','source':'user text in conversation','r03':'Case2 benefit is clear; accepted as new baseline','r02':'Cases9/10 slightly regressed; do not promote','exact_case_latencies':None,'complete_15_case_results_supplied':False}
b.write(b.OUT/'v12_r02_r03_feedback.json',json.dumps(feedback,ensure_ascii=False,indent=2)+'\n')
state=json.loads((b.OUT/'MAINLINE.json').read_text(encoding='utf-8'))
history=state.setdefault('historical_candidates',[])
if not any(x['version']=='v12_r02' for x in history):history.append({'version':'v12_r02','file':'v12_r02_case9_10_a_resident.asc','status':'user reported slight regression on9/10; rejected','feedback':'v12_r02_r03_feedback.json'})
state.update(accepted_sota=frozen.name,accepted_version='v12_r03',accepted_sha256=b.SHA,acceptance_basis='user explicitly accepted r03 as new baseline after clear Case2 improvement; exact timings and complete table not supplied',previous_sota='V12_BASELINE_R52.asc',candidates=[{'version':'v12_r04','file':candidate.name,'sha256':sha(candidate),'parent':frozen.name,'status':'CPU and host checks passed; device compilation and NPU evaluation pending'}])
b.write(b.OUT/'MAINLINE.json',json.dumps(state,ensure_ascii=False,indent=2)+'\n')
b.write(b.OUT/'v12_r04_audit.json',json.dumps({'parent_sha256':b.SHA,'candidate_sha256':sha(candidate),'r03_recovered_byte_for_byte':True,'r03_frozen_copy_identical':True,'R52_R43_hashes_unchanged':True,'event_callsites_match_original_R06':True,'test_hashes_match':True,'fault_injection_restored':True,'r02_not_inherited':True,'CANN_compiled':False,'NPU_tested':False},indent=2)+'\n')
print('r03 accepted and frozen; r04 audited and pending NPU evaluation.')

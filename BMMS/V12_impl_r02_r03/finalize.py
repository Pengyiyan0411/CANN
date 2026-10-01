from pathlib import Path
import hashlib,json
import build as b

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
raw=b.BASE.read_bytes();src=raw.decode().replace('\r\n','\n')
assert sha(b.BASE)==b.SHA
assert sha(b.ROOT/'BMMS_V11_R52/R52_SHORT_DOT_STATIC.asc')==b.SHA
assert sha(b.ROOT/'V11_analysis_r43/R43_CASE8_PADDED_MACRO.asc')=='15e2c9a0f73e7534c26400107389dcd8e5cf685b5f6f477c7a3684ad3991df2d'
host=json.loads((b.OUT/'v12_r02_r03_host_checks.json').read_text())
for r,mod in [(2,b.module2(src)),(3,b.module3(src))]:
    p=b.OUT/(b.NAMES[r]+'.asc');data=p.read_bytes()
    call=('bmms1202::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream)' if r==2 else 'bmms1203::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,stream)')
    hook=('    if('+call+')return;\r\n').encode()
    assert data.count(mod.encode())==1 and data.count(hook)==1
    assert data.replace(mod.encode(),b'',1).replace(hook,b'',1)==raw
    report=json.loads((b.OUT/f'v12_r0{r}_cpu_checks.json').read_text())
    assert report['source_sha256']==host['source_sha256'][b.NAMES[r]]==sha(p)
    extracted=b.between(mod,f'// BMMS120{r}_BEGIN',f'// BMMS120{r}_CPU_END')
    assert (b.H/f'r0{r}_extracted.hpp').read_text()==extracted

p=b.OUT/'MAINLINE.json';state=json.loads(p.read_text(encoding='utf-8'))
state['historical_candidates']=[{'version':'v12_r01','file':'V12_01_CASE12_DENSE.asc','status':'15/15 Pass; user reported no meaningful gain; not promoted','feedback':'../V12_results/2026-09-28_v1201_ranking/ANALYSIS.json'}]
for k in ['candidate','candidate_status','candidate_feedback']:state.pop(k,None)
state['candidates']=[{'version':f'v12_r0{r}','file':b.NAMES[r]+'.asc','sha256':sha(b.OUT/(b.NAMES[r]+'.asc')),'parent':'V12_BASELINE_R52.asc','status':'independent performance candidate; CPU and host checks passed; CANN/NPU pending'} for r in [2,3]]
state['naming']='v12_rxx; legacy V12.01 is r01; subsequent candidates r02/r03'
b.write(p,json.dumps(state,ensure_ascii=False,indent=2)+'\n')
b.write(b.OUT/'v12_r02_r03_audit.json',json.dumps({'parent_sha256':b.SHA,'R52_and_R43_frozen_hashes_unchanged':True,'both_parents_recovered_byte_for_byte':True,'test_source_hashes_match_deliverables':True,'CANN_compiled':False,'NPU_tested':False},indent=2)+'\n')
print('Artifacts audited; mainline remains R52.')

import hashlib,json
import build as b
raw=b.BASE.read_bytes();assert hashlib.sha256(raw).hexdigest()==b.SHA
candidate=b.OUT/(b.NAME+'.asc');data=candidate.read_bytes();old,new=b.changes(raw)
assert data.count(new)==1 and data.replace(new,old,1)==raw
digest=hashlib.sha256(data).hexdigest()
assert json.loads((b.OUT/'v12_r05_host_checks.json').read_text())['source_sha256']==digest
assert json.loads((b.OUT/'v12_r05_manifest.json').read_text())['sha256']==digest
assert (b.OUT/'v12_r03_case2_static_k.asc').read_bytes()==raw
assert hashlib.sha256((b.OUT/'v12_r04_case9_10_partial_a_cache.asc').read_bytes()).hexdigest()=='d4c0e539ca2145aa520e7b63c7a6bd8b9006ef3d54fa531971b1cf4c67720605'
p=b.OUT/'MAINLINE.json';d=json.loads(p.read_text(encoding='utf-8'))
d['active_diagnostic']={'version':'v12_r05','file':candidate.name,'sha256':digest,'parent':b.BASE.name,'purpose':'full r04 eligibility on original R06 plan; one-group real-computation stress','status':'host checks passed; CANN/NPU pending; not a performance baseline','readme':'v12_r05_README.md'}
d['naming']='v12_rxx; legacy V12.01 is r01; r03 accepted; r04 experimental; r05 diagnostic'
b.write(p,json.dumps(d,ensure_ascii=False,indent=2)+'\n')
print('r05 audited; r03 baseline and r04 candidate remain unchanged.')

import hashlib,json
from pathlib import Path
import build as b
def sha(x):return hashlib.sha256(x).hexdigest()
def main():
    raw=b.BASE.read_bytes();frozen=(b.OUT/'V12_BASELINE_R52.asc').read_bytes();candidate=(b.OUT/(b.NAME+'.asc')).read_bytes()
    assert raw==frozen and sha(raw)==b.SHA
    module=b.module().encode();hook=b'    if(bmms1201::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\r\n'
    assert candidate.count(module)==candidate.count(hook)==1
    assert candidate.replace(module,b'',1).replace(hook,b'',1)==raw
    for name in ['HOST_CHECKS.json','CPU_CHECKS.json']:
        r=json.loads((b.OUT/name).read_text());assert r['source_sha256']==sha(candidate)
    assert (b.H/'cpu_build/extracted.hpp').read_bytes()==(b.H/'extracted.hpp').read_bytes()
    r43=b.ROOT/'V11_analysis_r43/R43_CASE8_PADDED_MACRO.asc'
    assert sha(r43.read_bytes())=='15e2c9a0f73e7534c26400107389dcd8e5cf685b5f6f477c7a3684ad3991df2d'
    report={'candidate_sha256':sha(candidate),'accepted_baseline_sha256':sha(raw),'baseline_identical_to_R52':True,
        'removing_new_module_and_hook_recovers_R52_bytes':True,'R43_frozen_hash_unchanged':True,
        'test_reports_match_candidate':True,'fault_injection_header_restored':True,
        'accepted_mainline':'V12_BASELINE_R52.asc','candidate_status':'local checks passed; awaiting CANN/Judge',
        'CANN_compiled':False,'NPU_tested':False}
    b.write(b.OUT/'ARTIFACT_CHECKS.json',json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()

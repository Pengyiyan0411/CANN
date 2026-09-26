"""Verify exact candidate, evidence, and probe before making deterministic ZIPs."""
from pathlib import Path
import ast
import hashlib
import json
import zipfile
from build import HERE, ROOT, OUT, BASE, BASE_SHA, sha

def zipfiles(dest,items):
    with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name,p in sorted(items):
            info=zipfile.ZipInfo(name,date_time=(2026,9,26,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,p.read_bytes())
    with zipfile.ZipFile(dest) as z:
        assert z.testzip() is None
        for name,p in items:assert z.read(name)==p.read_bytes()
    return {'file':dest.name,'sha256':sha(dest),'bytes':dest.stat().st_size,'members':len(items)}

def main():
    manifest=json.loads((OUT/'MANIFEST.json').read_text(encoding='utf-8'))
    checks=json.loads((HERE/'CHECKS.json').read_text(encoding='utf-8'))
    probe=json.loads((HERE/'PROBE_OFFLINE_CHECKS.json').read_text(encoding='utf-8'))
    candidate=OUT/manifest['file'];assert sha(candidate)==manifest['sha256']==checks['source_sha256']
    assert sha(BASE)==sha(OUT/'P01_CONTROL.asc')==BASE_SHA
    fragment=(HERE/'reuse_fragment.asc').read_text(encoding='utf-8')
    source=candidate.read_text(encoding='utf-8')
    hook='    if(bmms11::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
    restored=source.split('\n',1)[1].replace(fragment+'\n','',1).replace(hook,'',1)
    assert restored==BASE.read_text(encoding='utf-8')
    assert source.count('extern "C" void run_kernel(')==1 and '#define ASCENDC_CUBE_ONLY' not in source
    assert 'Iterate' not in fragment and 'SetAtomic' not in fragment and '#include "catlass/' not in fragment
    r=checks['runs']['R01'];assert r['source_runs']==153 and r['repeat_pairs']==77 and r['plan_checks']==4494
    assert r['strict_misses']==r['combined_misses']==0 and r['known_precision_limitations']==3
    assert checks['cann_compiled'] is False and checks['npu_tested'] is False
    for path,digest in checks['artifacts'].items():assert sha(ROOT/path)==digest
    for path,digest in probe['files'].items():assert sha(ROOT/path)==digest
    for p in list(HERE.glob('*.py'))+list((HERE/'device_probe').glob('*.py')):ast.parse(p.read_text(encoding='utf-8'))
    submit=zipfiles(ROOT/'BMMS_V11_R01_提交包.zip',[(OUT.name+'/'+p.name,p) for p in OUT.iterdir() if p.is_file()])
    diagnostic=zipfiles(ROOT/'BMMS_V11_P01_R01_限时诊断包.zip',
        [('BMMS_V11_device_probe/'+p.name,p) for p in (HERE/'device_probe').iterdir() if p.is_file()])
    report={'submission':submit,'diagnostic':diagnostic,'fallback_restored_exactly':True,'cann_compiled':False,'npu_tested':False}
    (HERE/'PACKAGE_CHECKS.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2,ensure_ascii=False))

if __name__=='__main__':main()

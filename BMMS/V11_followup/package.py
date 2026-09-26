"""Freeze and verify independent R02/R03 submission sources and evidence."""
from pathlib import Path
import ast
import hashlib
import json
import zipfile

ROOT=Path(__file__).resolve().parents[1]
HERE=ROOT/'V11_followup';OUT=ROOT/'BMMS_V11_R02_R03'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    m=json.loads((OUT/'MANIFEST.json').read_text(encoding='utf-8'))
    checks=json.loads((HERE/'CHECKS.json').read_text(encoding='utf-8'))
    r01=(ROOT/'BMMS_V11_SubmitPack/R01_REUSE_2X2.asc').read_text(encoding='utf-8')
    assert sha(ROOT/'BMMS_V11_SubmitPack/R01_REUSE_2X2.asc')==m['base_sha256']
    for v in m['variants']:
        p=OUT/v['file'];assert sha(p)==v['sha256']==checks['sources'][p.name]
        text=p.read_text(encoding='utf-8')
        assert text.count('extern "C" void run_kernel(')==1 and '#define ASCENDC_CUBE_ONLY' not in text
    old=(ROOT/'V11_impl/reuse_fragment.asc').read_text(encoding='utf-8')
    macro=(HERE/'macro_ring_fragment.asc').read_text(encoding='utf-8')
    dense=(HERE/'residual_dense_fragment.asc').read_text(encoding='utf-8')
    r02=(OUT/'R02_MACRO_RING.asc').read_text(encoding='utf-8')
    restored=r02.replace(macro,old,1).replace('if(bmms11r2::TryLaunch','if(bmms11::TryLaunch',1)
    assert restored.split('\n',1)[1]==r01.split('\n',1)[1]
    r03=(OUT/'R03_RESIDUAL_DENSE.asc').read_text(encoding='utf-8')
    hook='    if(bmms11d::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
    assert r03.replace(dense+'\n','',1).replace(hook,'',1).split('\n',1)[1]==r01.split('\n',1)[1]
    for run in checks['runs'].values():
        assert run['source_runs']==169 and run['repeat_pairs']==85 and run['plan_checks']==4494 and run['guard_checks']==7560
        assert run['strict_misses']==run['combined_misses']==0 and run['known_precision_limitations']==3
    assert checks['negative_control']['early_free_rejected'] is True
    for path,digest in checks['artifacts'].items():assert sha(ROOT/path)==digest,path
    for p in HERE.glob('*.py'):ast.parse(p.read_text(encoding='utf-8'),filename=p.name)
    zip_path=ROOT/'BMMS_V11_R02_R03_提交包.zip'
    files=sorted(p for p in OUT.iterdir() if p.is_file())
    with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in files:
            info=zipfile.ZipInfo('BMMS_V11_R02_R03/'+p.name,date_time=(2026,9,26,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,p.read_bytes())
    with zipfile.ZipFile(zip_path) as z:
        assert z.testzip() is None
        for p in files:assert z.read('BMMS_V11_R02_R03/'+p.name)==p.read_bytes()
    report={'archive':zip_path.name,'sha256':sha(zip_path),'bytes':zip_path.stat().st_size,'members':len(files),
        'R01_source_restored_from_each_variant':True,'independent_variants':True,'cann_compiled_locally':False,'npu_tested_locally':False}
    (HERE/'PACKAGE_CHECKS.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(report,indent=2,ensure_ascii=False))

if __name__=='__main__':main()

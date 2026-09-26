"""Verify exact reviewed candidates and produce a deterministic submission ZIP."""
from pathlib import Path
import ast
import hashlib
import json
import zipfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
OUT=ROOT/'BMMS_V10_SubmitPack'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    m=json.loads((OUT/'MANIFEST.json').read_text(encoding='utf-8'))
    r=json.loads((OUT/'CPU_CHECKS.json').read_text(encoding='utf-8'))
    assert m['source_template_sha256']==sha(HERE/'streaming.asc.in')
    sources=[]
    for item in m['variants']:
        p=OUT/item['file'];row=r['runs'][item['variant']]
        assert sha(p)==item['sha256']==row['source_sha256']
        assert row['ordinary_source_runs']==512 and row['bitwise_repeat_pairs']==256
        assert row['plan_checks']==8190 and row['ordinary_strict_misses']==0
        assert row['known_precision_limitations_reproduced']==3
        assert row['cann_compiled'] is False and row['npu_tested'] is False
        src=p.read_text(encoding='utf-8')
        assert src.count('extern "C" void run_kernel(')==1
        assert '#define ASCENDC_CUBE_ONLY' not in src
        assert 'IterateAll' not in src and 'SetAtomic' not in src
        assert 'SyncAll<true>()' in src and 'GetTensorC<true>(c,0,true)' in src
        assert 'p.K);' in src and src.count('aclrtMalloc(')==1
        assert '#include "catlass/' not in src
        sources.append(src.split('\n',1)[1].replace('#define BMMS10_SPLIT_N 1','#define BMMS10_SPLIT_N 0'))
    assert sources[0]==sources[1], 'F01/F02 differ beyond selective N split'
    for name,digest in r['artifacts'].items():assert sha(ROOT/name)==digest
    for p in HERE.glob('*.py'):ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
    names=[x['file'] for x in m['variants']]+['MANIFEST.json','CPU_CHECKS.json','README.md']
    dest=ROOT/'BMMS_V10_提交包.zip'
    with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name in names:
            info=zipfile.ZipInfo('BMMS_V10_SubmitPack/'+name,date_time=(2026,9,26,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,(OUT/name).read_bytes())
    with zipfile.ZipFile(dest) as z:
        assert z.testzip() is None
        for name in names:assert z.read('BMMS_V10_SubmitPack/'+name)==(OUT/name).read_bytes()
    report={'archive':dest.name,'sha256':sha(dest),'bytes':dest.stat().st_size,
            'f01_f02_only_dispatch_difference':True,'cann_compiled':False,'npu_tested':False}
    (HERE/'PACKAGE_CHECKS.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2,ensure_ascii=False))

if __name__=='__main__':main()

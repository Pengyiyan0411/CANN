"""Pack exact sources and verification records; no build products or input tensors."""
from pathlib import Path
import ast,importlib.util,json,zipfile
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
spec=importlib.util.spec_from_file_location('resident_build',HERE/'build.py');build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)
def main():
    build.verify();manifest=json.loads((build.OUT/'MANIFEST.json').read_text(encoding='utf-8'))
    checks=json.loads((HERE/'CHECKS.json').read_text(encoding='utf-8'))
    assert checks==json.loads((build.OUT/'CPU_CHECKS.json').read_text(encoding='utf-8'))
    for row in [manifest['control'],*manifest['variants']]:
        assert build.sha(build.OUT/row['file'])==row['sha256']==checks['sources'][row['file']]
    for path,digest in checks['artifacts'].items():assert build.sha(ROOT/path)==digest,path
    for version,count in [('R14',554),('R17',640),('R18',752),('R19',554)]:
        run=checks['runs'][version];assert run['source_runs']==count
        assert run['strict_misses']==run['combined_misses']==0 and run['known_precision_limitations']==3
        data=json.loads((HERE/(version+'_CPU_RESULT.json')).read_text(encoding='utf-8'))
        assert {k:v for k,v in data.items() if k!='output_bits'}==run
    a=json.loads((HERE/'R14_CPU_RESULT.json').read_text(encoding='utf-8'))
    b=json.loads((HERE/'R19_CPU_RESULT.json').read_text(encoding='utf-8'))
    assert a['output_bits']==b['output_bits'] and checks['R14_R19_ordinary_outputs_equal_bitwise']
    assert all(x['rejected'] for x in checks['negative_controls'].values())
    assert build.sha(HERE/'INPUT_PLAN.md')==manifest['input_plan_sha256']
    for p in HERE.glob('*.py'):ast.parse(p.read_text(encoding='utf-8'),filename=p.name)
    files=sorted(p for p in build.OUT.iterdir() if p.is_file())
    assert {p.name for p in files}=={'README.md','MANIFEST.json','CPU_CHECKS.json','R14_CONTROL.asc',*(n+'.asc' for n in build.NAMES.values())}
    target=ROOT/'BMMS_V11_R17_R18_R19_提交包.zip'
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in files:
            e=zipfile.ZipInfo('BMMS_V11_R17_R18_R19/'+p.name,date_time=(2026,9,26,0,0,0))
            e.compress_type=zipfile.ZIP_DEFLATED;z.writestr(e,p.read_bytes())
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        for p in files:assert z.read('BMMS_V11_R17_R18_R19/'+p.name)==p.read_bytes()
    report={'file':target.name,'sha256':build.sha(target),'bytes':target.stat().st_size,'members':len(files),
        'R14_control_unchanged':True,'independent_R14_descendants':True,'cann_compiled_locally':False,'npu_tested_locally':False}
    build.write(HERE/'PACKAGE_CHECKS.json',json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()

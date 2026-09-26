"""Package R23, same-architecture K1, frozen R14 and independent geometry probes."""
from pathlib import Path
import ast,importlib.util,json,zipfile
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
spec=importlib.util.spec_from_file_location('builder',HERE/'build.py');build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)

def main():
    build.verify();manifest=json.loads((build.OUT/'MANIFEST.json').read_text(encoding='utf-8'))
    checks=json.loads((HERE/'CHECKS.json').read_text(encoding='utf-8'))
    assert checks==json.loads((build.OUT/'CPU_CHECKS.json').read_text(encoding='utf-8'))
    for row in manifest['files']:assert build.sha(build.OUT/row['file'])==row['sha256']==checks['sources'][row['file']]
    for rel,digest in checks['artifacts'].items():assert build.sha(ROOT/rel)==digest,rel
    outputs={}
    for version in ['R14','K1','R23']:
        r=checks['runs'][version];assert r['source_runs']==116 and r['repeat_checks']==58 and r['strict_misses']==0
        actual=json.loads((HERE/(version+'_CPU_RESULT.json')).read_text(encoding='utf-8'))
        assert {k:v for k,v in actual.items() if k!='output_bits'}==r;outputs[version]=actual['output_bits']
    assert outputs['R14']==outputs['K1'] and len(outputs['R14'])==58
    for key,bits in outputs['R14'].items():
        if not key.endswith('_3'):assert outputs['R23'][key]==bits
    assert all(r['rejected'] for r in checks['negative_controls'].values())
    dispatch=json.loads((HERE/'DISPATCH_CHECKS.json').read_text(encoding='utf-8'))
    assert dispatch==json.loads((build.OUT/'DISPATCH_CHECKS.json').read_text(encoding='utf-8'))
    for rel,digest in dispatch['sources'].items():assert build.sha(ROOT/rel)==digest,rel
    assert dispatch['wrong_dtype_fault_rejected'] and all(v['unique_device_bindings']==8 for v in dispatch['runs'].values())
    for p in HERE.glob('*.py'):ast.parse(p.read_text(encoding='utf-8'),filename=p.name)
    files=sorted(p for p in build.OUT.iterdir() if p.is_file())
    assert {p.name for p in files}=={r['file'] for r in manifest['files']}|{'README.md','MANIFEST.json','CPU_CHECKS.json','DISPATCH_CHECKS.json'}
    target=ROOT/'BMMS_V11_R23_提交包.zip'
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in files:
            item=zipfile.ZipInfo('BMMS_V11_R23/'+p.name,date_time=(2026,9,27,0,0,0));item.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(item,p.read_bytes())
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        for p in files:assert z.read('BMMS_V11_R23/'+p.name)==p.read_bytes()
    report={'file':target.name,'sha256':build.sha(target),'bytes':target.stat().st_size,'members':len(files),
            'R14_control_unchanged':True,'R23_from_R14':True,'four_independent_geometry_probes':True,
            'cann_compiled_locally':False,'npu_tested_locally':False}
    build.write(HERE/'PACKAGE_CHECKS.json',json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()

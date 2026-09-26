"""Package exact R22 source and R14 control with checks tied to source hashes."""
from pathlib import Path
import ast,importlib.util,json,shutil,zipfile
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
spec=importlib.util.spec_from_file_location('builder',HERE/'build.py');build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)
def main():
    build.verify();manifest=json.loads((build.OUT/'MANIFEST.json').read_text(encoding='utf-8'))
    checks=json.loads((HERE/'CHECKS.json').read_text(encoding='utf-8'))
    assert checks==json.loads((build.OUT/'CPU_CHECKS.json').read_text(encoding='utf-8'))
    for row in [manifest['control'],manifest['candidate']]:
        assert build.sha(build.OUT/row['file'])==row['sha256']==checks['sources'][row['file']]
    for rel,digest in checks['artifacts'].items():assert build.sha(ROOT/rel)==digest,rel
    outputs=[]
    for version in ['R14','R22']:
        r=checks['runs'][version];assert r['source_runs']==788 and r['repeat_pairs']==402
        assert r['strict_misses']==r['combined_misses']==0 and r['known_precision_limitations']==3
        actual=json.loads((HERE/(version+'_CPU_RESULT.json')).read_text(encoding='utf-8'))
        assert {k:v for k,v in actual.items() if k!='output_bits'}==r;outputs.append(actual['output_bits'])
    assert outputs[0]==outputs[1] and len(outputs[0])==386
    assert all(r['rejected'] for r in checks['negative_controls'].values())
    dispatch=json.loads((HERE/'DISPATCH_CHECKS.json').read_text(encoding='utf-8'))
    for rel,digest in dispatch['sources'].items():assert build.sha(ROOT/rel)==digest,rel
    assert dispatch['unique_device_bindings']==64 and dispatch['wrong_dtype_fault_rejected']
    shutil.copyfile(HERE/'DISPATCH_CHECKS.json',build.OUT/'DISPATCH_CHECKS.json')
    for p in HERE.glob('*.py'):ast.parse(p.read_text(encoding='utf-8'),filename=p.name)
    files=sorted(p for p in build.OUT.iterdir() if p.is_file())
    assert {p.name for p in files}=={'README.md','MANIFEST.json','CPU_CHECKS.json','DISPATCH_CHECKS.json','R14_CONTROL.asc','R22_SHAPE_SWITCH.asc'}
    target=ROOT/'BMMS_V11_R22_提交包.zip'
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in files:
            item=zipfile.ZipInfo('BMMS_V11_R22/'+p.name,date_time=(2026,9,27,0,0,0));item.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(item,p.read_bytes())
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        for p in files:assert z.read('BMMS_V11_R22/'+p.name)==p.read_bytes()
    report={'file':target.name,'sha256':build.sha(target),'bytes':target.stat().st_size,'members':len(files),
            'R14_control_unchanged':True,'R22_from_R14':True,'cann_compiled_locally':False,'npu_tested_locally':False}
    build.write(HERE/'PACKAGE_CHECKS.json',json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()

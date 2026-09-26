"""Package only the source and evidence bound to completed local checks."""
from pathlib import Path
import ast,importlib.util,json,zipfile
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
spec=importlib.util.spec_from_file_location('k_build',HERE/'build.py');build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)
def main():
    build.verify();manifest=json.loads((build.OUT/'MANIFEST.json').read_text(encoding='utf-8'))
    checks=json.loads((HERE/'CHECKS.json').read_text(encoding='utf-8'))
    assert checks==json.loads((build.OUT/'CPU_CHECKS.json').read_text(encoding='utf-8'))
    for row in [manifest['control'],*manifest['variants']]:
        assert build.sha(build.OUT/row['file'])==row['sha256']==checks['sources'][row['file']]
    for path,digest in checks['artifacts'].items():assert build.sha(ROOT/path)==digest,path
    old=json.loads((ROOT/'V11_single_wave/R11_CPU_RESULT.json').read_text(encoding='utf-8'))
    for version,added in [('R15',176),('R16',288)]:
        run=checks['runs'][version]
        assert run['source_runs']==452+added and run['repeat_pairs']==226+added//2
        assert run['strict_misses']==run['combined_misses']==0 and run['known_precision_limitations']==3
        assert run['reduction_checks']['checked']==22 and run['reduction_checks']['parallel_cases']==0
        data=json.loads((HERE/(version+'_CPU_RESULT.json')).read_text(encoding='utf-8'))
        assert {k:v for k,v in data.items() if k!='output_bits'}==run
        for key,bits in old['output_bits'].items():assert data['output_bits'][key]==bits
    assert all(x['rejected'] for x in checks['negative_controls'].values())
    for p in HERE.glob('*.py'):ast.parse(p.read_text(encoding='utf-8'),filename=p.name)
    files=sorted(p for p in build.OUT.iterdir() if p.is_file())
    assert {p.name for p in files}=={'README.md','MANIFEST.json','CPU_CHECKS.json','R11_CONTROL.asc','R15_K32_GAPS.asc','R16_K16_TAILS.asc'}
    target=ROOT/'BMMS_V11_R15_R16_提交包.zip'
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in files:
            e=zipfile.ZipInfo('BMMS_V11_R15_R16/'+p.name,date_time=(2026,9,26,0,0,0))
            e.compress_type=zipfile.ZIP_DEFLATED;z.writestr(e,p.read_bytes())
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        for p in files:assert z.read('BMMS_V11_R15_R16/'+p.name)==p.read_bytes()
    report={'file':target.name,'sha256':build.sha(target),'bytes':target.stat().st_size,'members':len(files),
        'R11_control_unchanged':True,'independent_R11_descendants':True,'cann_compiled_locally':False,'npu_tested_locally':False}
    build.write(HERE/'PACKAGE_CHECKS.json',json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()

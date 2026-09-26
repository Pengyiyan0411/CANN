"""Freeze independent R10 descendants with matching source and checker identities."""
from pathlib import Path
import ast
import importlib.util
import json
import zipfile
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
spec=importlib.util.spec_from_file_location('single_wave_build',HERE/'build.py')
build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)
def main():
    build.verify()
    manifest=json.loads((build.OUT/'MANIFEST.json').read_text(encoding='utf-8'))
    checks=json.loads((HERE/'CHECKS.json').read_text(encoding='utf-8'))
    assert checks==json.loads((build.OUT/'CPU_CHECKS.json').read_text(encoding='utf-8'))
    for row in [manifest['control'],*manifest['variants']]:
        assert build.sha(build.OUT/row['file'])==row['sha256']==checks['sources'][row['file']]
    for path,digest in checks['artifacts'].items():assert build.sha(ROOT/path)==digest,path
    outputs=[]
    for version,run in checks['runs'].items():
        assert run['source_runs']==452 and run['repeat_pairs']==226
        assert run['strict_misses']==run['combined_misses']==0 and run['known_precision_limitations']==3
        assert run['reduction_checks']['checked']==22
        assert run['reduction_checks']['parallel_cases']==(14 if version=='R12' else 0)
        data=json.loads((HERE/(version+'_CPU_RESULT.json')).read_text(encoding='utf-8'))
        assert {k:v for k,v in data.items() if k!='output_bits'}==run;outputs.append(data['output_bits'])
    assert outputs[0]==outputs[1]==outputs[2]
    assert all(n['rejected'] for n in checks['negative_controls'].values())
    assert checks['grid_checks']['checked']==6758 and checks['grid_checks']['changed']==154
    host=json.loads((HERE/'HOST_BENCH.json').read_text(encoding='utf-8'))
    for path,digest in host['source_sha256'].items():assert build.sha(ROOT/path)==digest,path
    for p in HERE.glob('*.py'):ast.parse(p.read_text(encoding='utf-8'),filename=p.name)
    files=sorted(p for p in build.OUT.iterdir() if p.is_file())
    assert {p.name for p in files}=={'README.md','MANIFEST.json','CPU_CHECKS.json','R10_CONTROL.asc',
        'R11_SINGLE_WAVE_EXPAND.asc','R12_PARALLEL_N_MERGE.asc'}
    path=ROOT/'BMMS_V11_R11_R12_提交包.zip'
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in files:
            entry=zipfile.ZipInfo('BMMS_V11_R11_R12/'+p.name,date_time=(2026,9,26,0,0,0))
            entry.compress_type=zipfile.ZIP_DEFLATED;z.writestr(entry,p.read_bytes())
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        for p in files:assert z.read('BMMS_V11_R11_R12/'+p.name)==p.read_bytes()
    report={'file':path.name,'sha256':build.sha(path),'bytes':path.stat().st_size,'members':len(files),
            'R10_control_unchanged':True,'independent_R10_descendants':True,
            'cann_compiled_locally':False,'npu_tested_locally':False}
    build.write(HERE/'PACKAGE_CHECKS.json',json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()

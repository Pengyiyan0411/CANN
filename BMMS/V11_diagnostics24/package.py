"""Package independent diagnostic sources, controls and exact-source checks."""
from pathlib import Path
import ast,importlib.util,json,zipfile
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
spec=importlib.util.spec_from_file_location('builder',HERE/'build.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
def main():
    b.verify();manifest=json.loads((b.OUT/'MANIFEST.json').read_text(encoding='utf-8'))
    cpu=json.loads((HERE/'CPU_CHECKS.json').read_text(encoding='utf-8'));host=json.loads((HERE/'HOST_CHECKS.json').read_text(encoding='utf-8'))
    assert cpu==json.loads((b.OUT/'CPU_CHECKS.json').read_text(encoding='utf-8'))
    assert host==json.loads((b.OUT/'HOST_CHECKS.json').read_text(encoding='utf-8'))
    for rel,digest in {**cpu['artifacts'],**host['source_sha256']}.items():assert b.sha(ROOT/rel)==digest,rel
    for row in manifest['probes']+manifest['controls']:assert b.sha(b.OUT/row['file'])==row['sha256']==cpu['sources'][row['file']]
    assert cpu['outputs_equal_bitwise'] and host['stale_task_count_fault_rejected']
    for p in HERE.glob('*.py'):ast.parse(p.read_text(encoding='utf-8'),filename=p.name)
    files=sorted(p for p in b.OUT.iterdir() if p.is_file())
    assert len(files)==28 and sum(p.suffix=='.asc' for p in files)==23
    archive=ROOT/'BMMS_V11_D24_诊断包.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in files:
            info=zipfile.ZipInfo(b.OUT.name+'/'+p.name,date_time=(2026,9,27,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,p.read_bytes())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for p in files:assert z.read(b.OUT.name+'/'+p.name)==p.read_bytes()
    report={'file':archive.name,'bytes':archive.stat().st_size,'sha256':b.sha(archive),'members':len(files),
        'diagnostics':21,'controls':2,'R14_R23_sources_frozen':True,'CANN_NPU_validated_locally':False}
    b.write(HERE/'PACKAGE_CHECKS.json',json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()

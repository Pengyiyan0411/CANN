"""Validate source-bound checks and package the exact reviewed candidate."""
from pathlib import Path
import ast,importlib.util,json,zipfile
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
s=importlib.util.spec_from_file_location('packet_pack_builder',HERE/'build.py');b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
def main():
    b.verify();docs={}
    for src,dst in [('CHECKS.json','CPU_CHECKS.json'),('HOST_CHECKS.json','HOST_CHECKS.json'),('BOUNDS_CHECKS.json','BOUNDS_CHECKS.json')]:
        d=json.loads((HERE/src).read_text(encoding='utf-8'));assert d==json.loads((b.OUT/dst).read_text(encoding='utf-8'));docs[src]=d
    cpu=docs['CHECKS.json'];host=docs['HOST_CHECKS.json'];bounds=docs['BOUNDS_CHECKS.json']
    manifest=json.loads((b.OUT/'MANIFEST.json').read_text(encoding='utf-8'))
    for name,digest in manifest['files'].items():assert b.sha(b.OUT/name)==digest==cpu['sources'][name]==host['sources'][name]
    assert bounds['source_sha256']==manifest['files'][b.NAME+'.asc']
    for rel,digest in cpu['artifacts'].items():assert b.sha(ROOT/rel)==digest,rel
    for name,digest in cpu['harness_headers'].items():assert b.sha(HERE/'cpu_build'/name)==digest,name
    assert b.sha(HERE/'check_host.py')==host['checker_sha256'] and b.sha(HERE/'check_bounds.py')==bounds['checker_sha256']
    assert cpu['ordinary_outputs_equal_R25_bitwise'] and host['Case5_metadata_records_equal_R25']
    original=b.BASE.read_text(encoding='utf-8');common=(HERE/'cpu_build/common_extracted.hpp').read_text(encoding='utf-8')
    producer=b.between(original,'template<class T,bool TA,bool TB,int TK>\nclass SmallKProducer','class SmallKConsumer {')
    assert producer in common
    oldfragment=b.between(original,'// BMMS25_BEGIN','// BMMS25_CPU_EXTRACT_END')
    assert oldfragment in (HERE/'cpu_build/targeted_extracted.hpp').read_text(encoding='utf-8')
    new=(b.OUT/(b.NAME+'.asc')).read_text(encoding='utf-8')
    assert b.between(new,'// BMMS26_BEGIN','// BMMS26_CPU_EXTRACT_END')==(HERE/'cpu_build/packet_extracted.hpp').read_text(encoding='utf-8')
    raw=(b.OUT/(b.NAME+'.asc')).read_bytes().decode('utf-8')
    restored=b.once(b.once(raw,b.fragment(original),''),b.NEW_HOOK,b.HOOK)
    assert restored.split('\n',1)[1].encode('utf-8')==b.BASE.read_bytes().split(b'\n',1)[1]
    for p in HERE.glob('*.py'):ast.parse(p.read_text(encoding='utf-8'),filename=p.name)
    assert (HERE/'DESIGN.md').read_bytes()==(b.OUT/'DESIGN.md').read_bytes()
    files=sorted(p for p in b.OUT.iterdir() if p.is_file());assert len(files)==8
    archive=ROOT/'BMMS_V11_R26_提交包.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in files:
            info=zipfile.ZipInfo(b.OUT.name+'/'+p.name,date_time=(2026,9,27,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,p.read_bytes())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and len(z.namelist())==len(files)
        for p in files:assert z.read(b.OUT.name+'/'+p.name)==p.read_bytes()
    report=dict(file=archive.name,sha256=b.sha(archive),bytes=archive.stat().st_size,files=len(files),zip_roundtrip_verified=True,
        inherited_CPU_source_exact_R25=True,candidate_sources_bound_to_CPU_host_bounds=True,composition=b.verify(),
        cann_compiled_locally=False,npu_tested_locally=False,platform_results_pending=True)
    b.write(HERE/'PACKAGE_CHECKS.json',json.dumps(report,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()

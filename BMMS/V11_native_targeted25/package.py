"""Bind delivery to completed exact-source checks, then round-trip the ZIP."""
from pathlib import Path
import ast,hashlib,importlib.util,json,zipfile
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
s=importlib.util.spec_from_file_location('pack_builder25',HERE/'build.py');b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
def main():
    b.verify();cpu=json.loads((HERE/'CHECKS.json').read_text(encoding='utf-8'));host=json.loads((HERE/'HOST_CHECKS.json').read_text(encoding='utf-8'))
    for doc,name in [(cpu,'CPU_CHECKS.json'),(host,'HOST_CHECKS.json')]:assert doc==json.loads((b.OUT/name).read_text(encoding='utf-8'))
    manifest=json.loads((b.OUT/'MANIFEST.json').read_text(encoding='utf-8'))
    for name,digest in manifest['files'].items():assert b.sha(b.OUT/name)==digest==cpu['source_files'][name]==host['sources'][name]
    for rel,digest in cpu['artifacts'].items():assert b.sha(ROOT/rel)==digest,rel
    for name,digest in cpu['harness_headers'].items():assert b.sha(HERE/'cpu_build'/name)==digest,name
    assert b.sha(HERE/'check_host.py')==host['checker_sha256']
    assert cpu['ordinary_outputs_equal_R23_bitwise'] and host['widened_guard_fault_rejected']
    original=b.BASE.read_text(encoding='utf-8');common=(HERE/'cpu_build/common_extracted.hpp').read_text(encoding='utf-8')
    # The inherited harness extracts the R14 Native code; prove it is exactly R23's.
    r14=(ROOT/'BMMS_V11_R13_R14/R14_FLEX_SINGLE_WAVE.asc').read_text(encoding='utf-8')
    assert b.between(original,'namespace bmms83 {','// [K,L] GEMV:')==b.between(r14,'namespace bmms83 {','// [K,L] GEMV:')
    producer=b.between(original,'template<class T,bool TA,bool TB,int TK>\nclass SmallKProducer','class SmallKConsumer {')
    consumer=b.between(original,'class SmallKPacketConsumer {','template<class T,bool TA,bool TB,int TK>\n__aicore__ inline void NativeEntry(')
    assert producer in common and consumer in common
    bounds=json.loads((HERE/'BOUNDS_CHECKS.json').read_text(encoding='utf-8'))
    assert bounds==json.loads((b.OUT/'BOUNDS_CHECKS.json').read_text(encoding='utf-8'))
    for p in HERE.glob('*.py'):ast.parse(p.read_text(encoding='utf-8'),filename=p.name)
    files=sorted(p for p in b.OUT.iterdir() if p.is_file());assert len(files)==10
    archive=ROOT/'BMMS_V11_R25_提交包.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in files:
            info=zipfile.ZipInfo(b.OUT.name+'/'+p.name,date_time=(2026,9,27,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,p.read_bytes())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and len(z.namelist())==len(files)
        for p in files:assert z.read(b.OUT.name+'/'+p.name)==p.read_bytes()
    report={'file':archive.name,'sha256':b.sha(archive),'bytes':archive.stat().st_size,'files':len(files),
        'zip_roundtrip_verified':True,'inherited_Native_CPU_source_exact_R23':True,
        'candidate_sources_bound_to_CPU_and_host_checks':True,'composition':b.verify(),
        'cann_compiled_locally':False,'npu_tested_locally':False,'platform_results_pending':True}
    b.write(HERE/'PACKAGE_CHECKS.json',json.dumps(report,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()

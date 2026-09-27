"""Package only after source and host reports identify the delivered bytes."""
from pathlib import Path
import importlib.util,json,zipfile
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
s=importlib.util.spec_from_file_location('multi_package_builder',HERE/'build.py');b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
def main():
    b.verify();sources={p.name:b.sha(p) for p in b.OUT.glob('*.asc')}
    cpu=json.loads((b.OUT/'CPU_CHECKS.json').read_text());host=json.loads((b.OUT/'HOST_CHECKS.json').read_text())
    assert cpu['sources']==host['sources']==sources
    assert cpu['outputs_equal_R25_bitwise_in_model'] and all(r['strict_misses']==0 for r in cpu['runs'].values())
    for name,digest in cpu['artifacts'].items():assert b.sha(HERE/name)==digest,name
    for name,digest in cpu['model_headers'].items():assert b.sha(HERE/'cpu_build'/name)==digest,name
    assert b.sha(HERE/'check_host.py')==host['checker_sha256']
    assert host['dispatch_checks']==80598 and host['widened_Native_B_guard_fault_rejected']
    manifest=json.loads((b.OUT/'MANIFEST.json').read_text())
    manifest.update(validation={'actual_source_runs_per_version':216,'repeat_checks_per_version':108,
        'source_runs_per_candidate':[80,68,68],'output_bits_equal_R25_in_model':True,
        'host_dispatch_checks':host['dispatch_checks'],'unchanged_non_target_records':host['unchanged_full_launch_records'],
        'negative_controls':4,'host_model_compiler':'g++ 15.2.0 (MSYS2 Rev13)'},
        candidate_promoted=False,checks_passed_locally=True,CANN_compiled_locally=False,NPU_tested_locally=False)
    manifest['delivery_files']={p.name:{'bytes':p.stat().st_size,'sha256':b.sha(p)} for p in sorted(b.OUT.iterdir()) if p.is_file() and p.name!='MANIFEST.json'}
    b.write(b.OUT/'MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    package=ROOT/'BMMS_V11_R29_R30_R31_提交包.zip'
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(b.OUT.iterdir()):
            if p.is_file():
                info=zipfile.ZipInfo(p.name,(2026,9,27,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,p.read_bytes())
    with zipfile.ZipFile(package) as z:
        assert z.testzip() is None
        for p in b.OUT.iterdir():
            if p.is_file():assert z.read(p.name)==p.read_bytes()
    print(json.dumps({'package':package.name,'sha256':b.sha(package),'files':len(list(b.OUT.iterdir()))}))
if __name__=='__main__':main()

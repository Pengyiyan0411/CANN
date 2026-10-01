"""Deliver checked R46 without modifying frozen or unrelated user candidates."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile
from build import BASE, OUT, ROOT, NAME, EXPECTED, sha, strip_additions


def main():
    candidate=(OUT/NAME).read_bytes()
    control=BASE.read_bytes()
    assert sha(control)==EXPECTED
    assert strip_additions(candidate.decode('utf-8')).encode('utf-8')==control
    checks=json.loads((OUT/'CPU_CHECKS.json').read_text(encoding='utf-8'))
    assert checks['source_sha256']==sha(candidate)
    assert checks['numeric_runs']==1584 and checks['exact_dyadic_oracle_mismatches']==0
    assert checks['planner_geometry_checks']==7350 and checks['guard_checks']==36960
    assert len(checks['faults_detected'])==2
    assert not checks['CANN_compiled'] and not checks['NPU_tested']
    manifest=json.loads((OUT/'MANIFEST.json').read_text(encoding='utf-8'))
    manifest['CPU_checks_sha256']=sha((OUT/'CPU_CHECKS.json').read_bytes())
    manifest['CPU_numeric_runs']=checks['numeric_runs']
    manifest['R25_preserved_sha256']=sha((ROOT/'BMMS_V11_R25/R25_NATIVE_TARGETED.asc').read_bytes())
    assert manifest['R25_preserved_sha256']=='7defd06457ddb0e356cbf4cc8407f31cbb7c622acf6efd66070be212fa4eacb2'
    manifest['representative_plan_columns']=['M','realN','K','tileM','vecN','pM','pN','workers','virtualN']
    (OUT/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

    # This was a user-reported Judge result; keep historical CPU results intact.
    r45_manifest=ROOT/'BMMS_V11_R45/MANIFEST.json'
    r45=json.loads(r45_manifest.read_text(encoding='utf-8'))
    r45['latest_user_feedback']={
        'date':'2026-09-28','case8_us':[62.54,62.47],
        'conclusion':'no_visible_gain','promoted':False,
        'all_case_pass_and_other_timings_supplied':False,
    }
    r45_manifest.write_text(json.dumps(r45,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

    downloads=ROOT.parent
    target=downloads/NAME
    if target.exists():
        assert target.read_bytes()==candidate, 'Refusing to overwrite another R46 file'
    else:
        target.write_bytes(candidate)
    assert (downloads/'R43_CASE8_PADDED_MACRO.asc').read_bytes()==control
    shutil.copyfile(OUT/'README.md',downloads/'R46_CASE8_说明.md')

    members=[p for p in OUT.iterdir() if p.is_file()]
    members+=[BASE,ROOT/'next_stage/cpu_shim.hpp']
    impl=ROOT/'V11_impl_r46'
    members += [impl/n for n in ['build.py','host.inc','launch.inc','check.py',
        'check_driver.cpp','tiling_stub.hpp','package.py','cpu_build/compile.log','cpu_build/run.log']]
    members += [ROOT/'V11_results/2026-09-28_r45_case8_feedback/FEEDBACK.json']
    archive=ROOT/'BMMS_V11_R46.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in members:z.write(p,p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert z.read('BMMS_V11_R46/'+NAME)==candidate
        assert z.read('BMMS_V11_R46/CONTROL_R43.asc')==control
    shutil.copyfile(archive,downloads/archive.name)
    print(json.dumps({'standalone':str(target),'source_sha256':sha(candidate),
        'zip':str(downloads/archive.name),'members':len(members),
        'source_bytes':len(candidate),'CANN_compiled':False,'NPU_tested':False}))


if __name__=='__main__':main()

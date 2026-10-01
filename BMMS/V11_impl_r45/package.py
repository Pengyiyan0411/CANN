"""Package the checked candidate without changing any source baseline."""
from pathlib import Path
import hashlib
import json
import zipfile
from build import ROOT, OUT, BASE, NAME, EXPECTED

HERE = Path(__file__).resolve().parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    candidate = (OUT/NAME).read_bytes()
    checks = json.loads((OUT/'CPU_CHECKS.json').read_text(encoding='utf-8'))
    assert sha(candidate) == checks['candidate_sha256']
    assert sha(BASE.read_bytes()) == EXPECTED
    assert sha((ROOT.parent/'R43_CASE8_PADDED_MACRO.asc').read_bytes()) == EXPECTED
    assert sha((ROOT/'BMMS_V11_R25/R25_NATIVE_TARGETED.asc').read_bytes()) == '7defd06457ddb0e356cbf4cc8407f31cbb7c622acf6efd66070be212fa4eacb2'
    assert (OUT/'CONTROL_R43.asc').read_bytes() == BASE.read_bytes()
    download = ROOT.parent/NAME
    if download.exists():
        assert download.read_bytes() == candidate, 'Refusing to replace an unrelated Downloads file'
    download.write_bytes(candidate)
    members = sorted(OUT.iterdir()) + [HERE/name for name in
        ['build.py','check.py','pack_model.hpp','check_driver.cpp','package.py']]
    members += [BASE]
    assert all(p.is_file() for p in members)
    archive = ROOT/'BMMS_V11_R45.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in members:
            z.writestr(p.relative_to(ROOT).as_posix(),p.read_bytes())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for p in members:
            assert z.read(p.relative_to(ROOT).as_posix()) == p.read_bytes()
    print(json.dumps({'standalone':str(download),'package':str(archive),
        'candidate_sha256':sha(candidate),'verified_package_files':len(members),
        'original_R43_and_R25_unchanged':True,'device_validation_pending':True}))


if __name__=='__main__':
    main()

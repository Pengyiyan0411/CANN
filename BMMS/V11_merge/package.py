"""Verify the frozen composition and build a deterministic R04 submission ZIP."""
from pathlib import Path
import ast
import importlib.util
import json
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
spec = importlib.util.spec_from_file_location('merge_build', HERE / 'build.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


def main():
    proof = build.verify()
    manifest = json.loads((build.OUT / 'MANIFEST.json').read_text(encoding='utf-8'))
    checks = json.loads((HERE / 'CHECKS.json').read_text(encoding='utf-8'))
    raw = json.loads((HERE / 'R04_CPU_RESULT.json').read_text(encoding='utf-8'))
    assert checks == json.loads((build.OUT / 'CPU_CHECKS.json').read_text(encoding='utf-8'))
    assert build.sha(build.SOURCE) == manifest['sha256'] == checks['source_sha256']
    assert {k: v for k, v in raw.items() if k != 'output_bits'} == checks['run']
    assert checks['run']['source_runs'] == 173 and checks['run']['strict_misses'] == 0
    assert checks['negative_control']['early_free_rejected']
    for rel, digest in checks['artifacts'].items():
        assert build.sha(ROOT / rel) == digest, rel
    for path in HERE.glob('*.py'):
        ast.parse(path.read_text(encoding='utf-8'), filename=path.name)
    target = ROOT / 'BMMS_V11_R04_提交包.zip'
    files = sorted(path for path in build.OUT.iterdir() if path.is_file())
    assert {p.name for p in files} == {'R04_MACRO_RING_RESIDUAL.asc', 'README.md', 'MANIFEST.json', 'CPU_CHECKS.json'}
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            entry = zipfile.ZipInfo('BMMS_V11_R04/' + path.name, date_time=(2026, 9, 26, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, path.read_bytes())
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        for path in files:
            assert archive.read('BMMS_V11_R04/' + path.name) == path.read_bytes()
    report = {'archive': target.name, 'sha256': build.sha(target), 'bytes': target.stat().st_size,
              'members': len(files), 'source_sha256': build.sha(build.SOURCE), 'composition': proof,
              'cann_compiled_locally': False, 'npu_tested_locally': False}
    build.write(HERE / 'PACKAGE_CHECKS.json', json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()

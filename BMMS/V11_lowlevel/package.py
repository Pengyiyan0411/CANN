"""Freeze two independent experimental descendants and their source-bound checks."""
from pathlib import Path
import ast
import importlib.util
import json
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
spec = importlib.util.spec_from_file_location('lowlevel_build', HERE / 'build.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


def main():
    build.verify()
    manifest = json.loads((build.OUT / 'MANIFEST.json').read_text(encoding='utf-8'))
    checks = json.loads((HERE / 'CHECKS.json').read_text(encoding='utf-8'))
    assert checks == json.loads((build.OUT / 'CPU_CHECKS.json').read_text(encoding='utf-8'))
    for row in manifest['variants']:
        assert build.sha(build.OUT / row['file']) == row['sha256'] == checks['sources'][row['file']]
    for path, digest in checks['artifacts'].items():
        assert build.sha(ROOT / path) == digest, path
    outputs = []
    for version, run in checks['runs'].items():
        assert run['source_runs'] == 256 and run['strict_misses'] == run['combined_misses'] == 0
        assert run['known_precision_limitations'] == 3
        data = json.loads((HERE / (version + '_CPU_RESULT.json')).read_text(encoding='utf-8'))
        assert {k:v for k,v in data.items() if k != 'output_bits'} == run
        outputs.append(data['output_bits'])
    assert outputs[0] == outputs[1] == outputs[2]
    assert all(row['rejected'] for row in checks['negative_controls'].values())
    for path in HERE.glob('*.py'):
        ast.parse(path.read_text(encoding='utf-8'), filename=path.name)
    archive = ROOT / 'BMMS_V11_R05_R06_提交包.zip'
    files = sorted(path for path in build.OUT.iterdir() if path.is_file())
    assert {p.name for p in files} == {'README.md','MANIFEST.json','CPU_CHECKS.json',*[v+'.asc' for v in build.NAMES.values()]}
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as output:
        for path in files:
            entry = zipfile.ZipInfo('BMMS_V11_R05_R06/' + path.name, date_time=(2026,9,26,0,0,0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            output.writestr(entry, path.read_bytes())
    with zipfile.ZipFile(archive) as output:
        assert output.testzip() is None
        for path in files:
            assert output.read('BMMS_V11_R05_R06/' + path.name) == path.read_bytes()
    report = {'file': archive.name, 'sha256': build.sha(archive), 'bytes': archive.stat().st_size,
              'members': len(files), 'independent_R04_descendants': True,
              'base_sha256': build.BASE_SHA, 'cann_compiled_locally': False, 'npu_tested_locally': False}
    build.write(HERE / 'PACKAGE_CHECKS.json', json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()

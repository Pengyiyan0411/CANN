"""Compose frozen R02 with the disjoint R03 residual branch, without retuning."""
from pathlib import Path
import difflib
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / 'BMMS_V11_R04'
SOURCE = OUT / 'R04_MACRO_RING_RESIDUAL.asc'
R02 = ROOT / 'BMMS_V11_R02_R03/R02_MACRO_RING.asc'
R03 = ROOT / 'BMMS_V11_R02_R03/R03_RESIDUAL_DENSE.asc'
PARENTS = {
    R02: '7e0c3e51e763170973c97d85836b1d217c0746da063352c5e392459a669220e5',
    R03: '233cb1d95ab788338958f6747a662578c5b1ee0e7e05ba8bef9d26f832c04fac',
    ROOT / 'BMMS_V11_R02_R03_提交包.zip': '1f24788789e35b056510f0c4f56501d56e13d226905824821641af1e0d4693a7',
}
HOOK = '    if(bmms11r2::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
EXTRA = '    if(bmms11d::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def once(text, old, new):
    assert text.count(old) == 1, (text.count(old), old)
    return text.replace(old, new, 1)


def write(path, text):
    path.write_text(text, encoding='utf-8', newline='\n')


def verify():
    for path, digest in PARENTS.items():
        assert sha(path) == digest, path
    r02 = R02.read_text(encoding='utf-8')
    r03 = R03.read_text(encoding='utf-8')
    macro = (ROOT / 'V11_followup/macro_ring_fragment.asc').read_text(encoding='utf-8')
    original = (ROOT / 'V11_followup/residual_dense_fragment.asc').read_text(encoding='utf-8')
    residual = (HERE / 'residual_dense_fragment.asc').read_text(encoding='utf-8')
    source = SOURCE.read_text(encoding='utf-8')
    assert r02.count(macro) == source.count(macro) == 1
    assert r03.count(original) == 1
    assert once(residual, '!bmms11r2::Eligible(', '!bmms11::Eligible(') == original
    restored = once(once(source, residual + '\n', ''), EXTRA, '')
    assert restored.split('\n', 1)[1] == r02.split('\n', 1)[1]
    assert source.count(HOOK + EXTRA) == 1
    assert source.count('extern "C" void run_kernel(') == 1
    assert '#define ASCENDC_CUBE_ONLY' not in source
    return {'R02_body_preserved': True, 'R03_residual_only_eligible_namespace_changed': True,
            'runtime_dispatch_order': ['R02_macro_ring', 'R03_residual_dense', 'P01_fallback'],
            'new_tuning_or_arithmetic_changes': False}


def main():
    for path, digest in PARENTS.items():
        assert sha(path) == digest, path
    r02 = R02.read_text(encoding='utf-8')
    old = (ROOT / 'V11_followup/residual_dense_fragment.asc').read_text(encoding='utf-8')
    residual = once(old, '!bmms11::Eligible(', '!bmms11r2::Eligible(')
    write(HERE / 'residual_dense_fragment.asc', residual)
    source = once(r02, 'extern "C" void run_kernel(', residual + '\nextern "C" void run_kernel(')
    source = once(source, HOOK, HOOK + EXTRA)
    source = once(source, r02.split('\n', 1)[0],
                  '// R04_MACRO_RING_RESIDUAL: combine user-confirmed R02 and the disjoint R03 residual branch.')
    OUT.mkdir(exist_ok=True)
    write(SOURCE, source)
    proof = verify()
    write(HERE / 'R04_vs_R02.diff', ''.join(difflib.unified_diff(
        r02.splitlines(True), source.splitlines(True), fromfile='R02_MACRO_RING', tofile=SOURCE.stem)))
    manifest = {'variant': SOURCE.stem, 'file': SOURCE.name, 'sha256': sha(SOURCE),
                'parents': {p.relative_to(ROOT).as_posix(): h for p, h in PARENTS.items()},
                'composition_proof': proof, 'ring_bytes_per_group': {'macro': 262144, 'residual': 65536},
                'cann_compiled_locally': False, 'npu_tested_locally': False,
                'platform_result_received': False, 'known_numerical_limitations_remain': True}
    write(OUT / 'MANIFEST.json', json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()

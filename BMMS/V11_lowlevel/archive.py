"""Append the contextual R04 result and independent low-level experiments to CANN/v11."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    subprocess.run([sys.executable, str(ROOT / 'V11_merge/archive.py'), '--repo', str(repo)], check=True)
    out = repo / 'BMMS'
    path = out / 'ARCHIVE_MANIFEST.json'
    manifest = json.loads(path.read_text(encoding='utf-8'))
    entries = {row['path']:row for row in manifest['files']}
    selected = []
    for folder in ['V11_lowlevel','BMMS_V11_R05_R06']:
        selected.extend(p for p in (ROOT / folder).iterdir() if p.is_file())
    selected.extend(ROOT / name for name in ['BMMS_V11_R05_R06_提交包.zip','audit_current/AUDIT_R04_DELIVERY.md'])
    for source in sorted(set(selected)):
        assert source.suffix not in ['.pyc','.exe','.bin']
        relative = source.relative_to(ROOT)
        destination = out / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        assert source.read_bytes() == destination.read_bytes()
        entries[relative.as_posix()] = {'path': relative.as_posix(), 'bytes':source.stat().st_size,
                                      'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
    manifest['scope'] = 'V9/V10/V11 history, contextual R04 platform result, independent R05 deferred-max and R06 macro-MMAD candidates'
    manifest['platform_source_identity'] = 'explicit user version labels where available; R04 inferred from sole preceding candidate; no platform source digest provided'
    manifest['files'] = [entries[name] for name in sorted(entries)]
    for row in manifest['files']:
        assert hashlib.sha256((out / row['path']).read_bytes()).hexdigest() == row['sha256']
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    shutil.copyfile(ROOT / 'V11_lowlevel/CANN_README.md', repo / 'README.md')
    ignore = repo / '.gitignore'
    text = ignore.read_text(encoding='utf-8')
    if 'BMMS/V11_lowlevel/cpu_build/' not in text:
        text += 'BMMS/V11_lowlevel/cpu_build/\n'
    ignore.write_text(text, encoding='utf-8')
    print(json.dumps({'branch':manifest['branch'], 'files_verified':len(entries)}))


if __name__ == '__main__':
    main()

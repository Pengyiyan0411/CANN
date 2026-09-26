"""Append R02/R03 feedback and the R04 composition to the authorized CANN/v11 archive."""
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
    subprocess.run([sys.executable, str(ROOT / 'V11_followup/archive.py'), '--repo', str(repo)], check=True)
    out = repo / 'BMMS'
    manifest = out / 'ARCHIVE_MANIFEST.json'
    info = json.loads(manifest.read_text(encoding='utf-8'))
    entries = {entry['path']: entry for entry in info['files']}
    sources = []
    for folder in ['V11_merge', 'BMMS_V11_R04']:
        sources.extend(p for p in (ROOT / folder).iterdir() if p.is_file())
    sources.extend(ROOT / p for p in ['BMMS_V11_R04_提交包.zip', 'audit_current/AUDIT_R02_R03_DELIVERY.md'])
    for source in sorted(set(sources)):
        assert source.suffix not in ['.exe', '.bin', '.pyc']
        rel = source.relative_to(ROOT)
        destination = out / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        assert source.read_bytes() == destination.read_bytes()
        entries[rel.as_posix()] = {'path': rel.as_posix(), 'bytes': source.stat().st_size,
                                  'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
    info['scope'] = 'V9/V10/V11 history, explicitly labelled feedback through R02/R03, R04 composed candidate pending platform result'
    info['files'] = [entries[k] for k in sorted(entries)]
    for entry in info['files']:
        assert hashlib.sha256((out / entry['path']).read_bytes()).hexdigest() == entry['sha256']
    manifest.write_text(json.dumps(info, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    shutil.copyfile(ROOT / 'V11_merge/CANN_README.md', repo / 'README.md')
    ignore = repo / '.gitignore'
    text = ignore.read_text(encoding='utf-8')
    line = 'BMMS/V11_merge/cpu_build/'
    if line not in text:
        text += line + '\n'
    ignore.write_text(text, encoding='utf-8')
    print(json.dumps({'branch': info['branch'], 'files_verified': len(entries),
                      'bytes': sum(entry['bytes'] for entry in entries.values())}))


if __name__ == '__main__':
    main()

"""Append D24 L00/L05 evidence, preserving historical sources and packages."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PREVIOUS = '26955f4b6c441ec890de30893cd8c7e5cde46434'
AUDIT = 'BatchMatmulMaxSum_当前审计报告_2026-09-26.md'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True, type=Path)
    repo = parser.parse_args().repo.resolve()
    out = repo / 'BMMS'
    old_manifest = subprocess.check_output(['git','show',PREVIOUS+':BMMS/ARCHIVE_MANIFEST.json'],cwd=repo)
    manifest = json.loads(old_manifest)
    entries = {x['path']:x for x in manifest['files']}
    assert len(entries) == 767
    snapshot = ROOT / 'audit_current/AUDIT_D24_R7.md'
    old_audit = subprocess.check_output(['git','show',PREVIOUS+':BMMS/'+AUDIT],cwd=repo)
    if snapshot.exists():
        assert snapshot.read_bytes() == old_audit
    else:
        snapshot.write_bytes(old_audit)
    changed = []
    for rel, row in list(entries.items()):
        source = ROOT / rel
        if sha(source) != row['sha256']:
            assert rel in {'README.md',AUDIT}, rel
            changed.append(rel)
            shutil.copyfile(source,out/rel)
            entries[rel] = {'path':rel,'bytes':source.stat().st_size,'sha256':sha(source)}
        else:
            assert sha(out/rel) == row['sha256'], rel
    added = [snapshot]
    for folder in ['V11_d24_l','V11_results/2026-09-27_d24_l00_l05']:
        added.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    for source in sorted(added):
        assert source.suffix not in {'.exe','.pyc','.bin'}
        rel = source.relative_to(ROOT).as_posix()
        assert rel not in entries, rel
        dest = out/rel
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,dest)
        entries[rel] = {'path':rel,'bytes':source.stat().st_size,'sha256':sha(source)}
    manifest['scope'] = 'D24 L00/L05 explicit results: Case15 single spatial task confirmed; skip unrun L01/L02/L03; frozen R25 retained; original L04/L06 next; no new kernel or device test'
    manifest['files'] = [entries[k] for k in sorted(entries)]
    for row in manifest['files']:
        for base in [ROOT,out]:
            p = base/row['path']
            assert sha(p) == row['sha256'] and p.stat().st_size == row['bytes'], row['path']
    manifest_newline = '\r\n' if b'\r\n' in old_manifest else '\n'
    (out/'ARCHIVE_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline=manifest_newline)
    readme = (ROOT/'README.md').read_text(encoding='utf-8')
    readme = re.sub(r'\]\((?!https?://)([^)]+)\)',r'](BMMS/\1)',readme)
    (repo/'README.md').write_text(readme,encoding='utf-8',newline='\n')
    print(json.dumps({'files_verified':len(entries),'changed_old_entries':changed,'old_sources_and_packages_frozen':True},ensure_ascii=True))


if __name__ == '__main__':
    main()

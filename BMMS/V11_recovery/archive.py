"""Append R07/R08 feedback and R09/R10 delivery while retaining all frozen prior bytes."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
PREVIOUS_ARCHIVE_COMMIT='d0069ec214a9db9c01a67fdd4af7c41fed038708'
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);args=ap.parse_args()
    repo=args.repo.resolve();out=repo/'BMMS';path=out/'ARCHIVE_MANIFEST.json'
    # Compare with the frozen parent commit, so rebuilding the current delivery is idempotent.
    previous=json.loads(subprocess.check_output(
        ['git','show',PREVIOUS_ARCHIVE_COMMIT+':BMMS/ARCHIVE_MANIFEST.json'],cwd=repo))
    subprocess.run([sys.executable,str(ROOT/'V11_grid_packets/archive.py'),'--repo',str(repo)],check=True)
    manifest=json.loads(path.read_text(encoding='utf-8'));entries={r['path']:r for r in manifest['files']}
    sources=[]
    for folder in ['V11_recovery','BMMS_V11_R09_R10']:
        sources.extend(p for p in (ROOT/folder).iterdir() if p.is_file())
    sources.extend(ROOT/p for p in ['BMMS_V11_R09_R10_提交包.zip','audit_current/AUDIT_R07_R08_DELIVERY.md'])
    for p in sorted(set(sources)):
        assert p.suffix not in ['.exe','.bin','.pyc']
        rel=p.relative_to(ROOT);dst=out/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst)
        assert p.read_bytes()==dst.read_bytes()
        entries[rel.as_posix()]={'path':rel.as_posix(),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    changed=[]
    for row in previous['files']:
        assert row['path'] in entries
        if row['sha256']!=entries[row['path']]['sha256']:changed.append(row['path'])
    assert set(changed)<=set(['README.md','BatchMatmulMaxSum_当前审计报告_2026-09-26.md']),changed
    manifest['scope']='V9/V10/V11 history; R07 case-5 runtime TLE; R08 15-pass single observation; independent R09 residual packets and R10 single-wave-grid candidates with frozen R08 control'
    manifest['files']=[entries[k] for k in sorted(entries)]
    for r in manifest['files']:
        assert hashlib.sha256((out/r['path']).read_bytes()).hexdigest()==r['sha256']
        assert hashlib.sha256((ROOT/r['path']).read_bytes()).hexdigest()==r['sha256']
    path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    shutil.copyfile(ROOT/'V11_recovery/CANN_README.md',repo/'README.md')
    ignore=repo/'.gitignore';text=ignore.read_text(encoding='utf-8')
    if 'BMMS/V11_recovery/cpu_build/' not in text:text+='BMMS/V11_recovery/cpu_build/\n'
    ignore.write_text(text,encoding='utf-8')
    print(json.dumps({'branch':manifest['branch'],'files_verified':len(entries),'changed_prior_entries':changed},ensure_ascii=False))
if __name__=='__main__':main()

"""Append user-labelled R05/R06 evidence, R07/R08 sources and controlled-comparison instructions."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);args=ap.parse_args()
    repo=args.repo.resolve()
    subprocess.run([sys.executable,str(ROOT/'V11_lowlevel/archive.py'),'--repo',str(repo)],check=True)
    out=repo/'BMMS';path=out/'ARCHIVE_MANIFEST.json'
    manifest=json.loads(path.read_text(encoding='utf-8'));entries={r['path']:r for r in manifest['files']}
    sources=[]
    for folder in ['V11_grid_packets','BMMS_V11_R07_R08']:
        sources.extend(p for p in (ROOT/folder).iterdir() if p.is_file())
    sources.extend(ROOT/p for p in ['BMMS_V11_R07_R08_提交包.zip','audit_current/AUDIT_R05_R06_DELIVERY.md'])
    for p in sorted(set(sources)):
        assert p.suffix not in ['.exe','.bin','.pyc']
        rel=p.relative_to(ROOT);dst=out/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst)
        assert p.read_bytes()==dst.read_bytes()
        entries[rel.as_posix()]={'path':rel.as_posix(),'bytes':p.stat().st_size,
                               'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    manifest['scope']='V9/V10/V11 history; labelled R05/R06 pass with uncertain speedup; R07 grid and R08 native packet candidates plus frozen R04 control'
    manifest['files']=[entries[k] for k in sorted(entries)]
    for r in manifest['files']:assert hashlib.sha256((out/r['path']).read_bytes()).hexdigest()==r['sha256']
    path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    shutil.copyfile(ROOT/'V11_grid_packets/CANN_README.md',repo/'README.md')
    ignore=repo/'.gitignore';text=ignore.read_text(encoding='utf-8')
    if 'BMMS/V11_grid_packets/cpu_build/' not in text:text+='BMMS/V11_grid_packets/cpu_build/\n'
    ignore.write_text(text,encoding='utf-8')
    print(json.dumps({'branch':manifest['branch'],'files_verified':len(entries)}))
if __name__=='__main__':main()

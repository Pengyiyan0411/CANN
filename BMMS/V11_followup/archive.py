"""Append R01 platform evidence and independent R02/R03 candidates to CANN/v11."""
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
    subprocess.run([sys.executable,str(ROOT/'V11_impl/archive.py'),'--repo',str(repo)],check=True)
    out=repo/'BMMS';mp=out/'ARCHIVE_MANIFEST.json'
    info=json.loads(mp.read_text(encoding='utf-8'));entries={r['path']:r for r in info['files']}
    sources=[]
    for folder in ['V11_followup','BMMS_V11_R02_R03']:
        sources.extend(p for p in (ROOT/folder).iterdir() if p.is_file())
    sources.extend(p for p in (ROOT/'V11_results').rglob('*') if p.is_file())
    sources.extend(ROOT/p for p in ['BMMS_V11_R02_R03_提交包.zip','audit_current/AUDIT_R01_DELIVERY.md'])
    for src in sorted(set(sources)):
        assert src.suffix not in ['.exe','.bin','.pyc']
        rel=src.relative_to(ROOT);dst=out/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
        assert src.read_bytes()==dst.read_bytes()
        entries[rel.as_posix()]={'path':rel.as_posix(),'bytes':src.stat().st_size,'sha256':hashlib.sha256(src.read_bytes()).hexdigest()}
    info['scope']='V9/V10/V11 sources and labelled feedback through R01; independent R02/R03 experimental descendants'
    info['files']=[entries[k] for k in sorted(entries)]
    for f in info['files']:assert hashlib.sha256((out/f['path']).read_bytes()).hexdigest()==f['sha256']
    mp.write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    ignore=repo/'.gitignore';s=ignore.read_text(encoding='utf-8');line='BMMS/V11_followup/cpu_build/'
    if line not in s:s+=line+'\n'
    ignore.write_text(s,encoding='utf-8')
    print(json.dumps({'branch':info['branch'],'files_verified':len(entries),'bytes':sum(f['bytes'] for f in entries.values())}))

if __name__=='__main__':main()

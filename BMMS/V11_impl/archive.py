"""Archive the reviewed R01 and F01 evidence without generated binaries/data."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',required=True,type=Path);args=ap.parse_args()
    repo=args.repo.resolve()
    subprocess.run([sys.executable,str(ROOT/'V9_impl/archive_to_repo.py'),'--repo',str(repo),'--with-v10'],check=True)
    selected=[]
    for folder in ['V11_impl','V11_impl/device_probe','BMMS_V11_SubmitPack']:
        selected.extend(p for p in (ROOT/folder).iterdir() if p.is_file())
    selected.extend(p for p in (ROOT/'V10_results').rglob('*') if p.is_file())
    selected.extend(ROOT/p for p in ['BMMS_V11_R01_提交包.zip','BMMS_V11_P01_R01_限时诊断包.zip',
        'audit_current/AUDIT_BEFORE_V11.md','audit_current/README_BEFORE_V11.md'])
    out=repo/'BMMS';manifest=out/'ARCHIVE_MANIFEST.json'
    info=json.loads(manifest.read_text(encoding='utf-8'));files={v['path']:v for v in info['files']}
    for src in sorted(set(selected)):
        assert src.suffix not in ['.exe','.pyc','.bin']
        rel=src.relative_to(ROOT);dest=out/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest)
        assert src.read_bytes()==dest.read_bytes()
        files[rel.as_posix()]={'path':rel.as_posix(),'bytes':src.stat().st_size,'sha256':hashlib.sha256(src.read_bytes()).hexdigest()}
    info['scope']='V9/V10/V11 candidates, P01 control, F01 user-confirmed result, source CPU checks, bounded device-probe source'
    info['excluded']='generated binaries/input tensors/CPU build directories/caches/external SDK and CATLASS checkouts'
    info['files']=[files[k] for k in sorted(files)]
    for item in info['files']:
        assert hashlib.sha256((out/item['path']).read_bytes()).hexdigest()==item['sha256']
    manifest.write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    ignore=repo/'.gitignore';text=ignore.read_text(encoding='utf-8')
    for line in ['BMMS/V11_impl/cpu_build/','BMMS/V11_impl/probe_prepare_check/','BMMS/V11_impl/device_probe/run/']:
        if line not in text:text+=line+'\n'
    ignore.write_text(text,encoding='utf-8')
    print(json.dumps({'branch':info['branch'],'files_verified':len(files),'bytes':sum(v['bytes'] for v in files.values())}))

if __name__=='__main__':main()

"""Append the user-selected R14 baseline and three independent descendants."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
PREVIOUS='e8782205d6477e86e3de31bdcad7c736087a1047'
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);args=ap.parse_args()
    repo=args.repo.resolve();out=repo/'BMMS';path=out/'ARCHIVE_MANIFEST.json'
    previous=json.loads(subprocess.check_output(['git','show',PREVIOUS+':BMMS/ARCHIVE_MANIFEST.json'],cwd=repo))
    subprocess.run([sys.executable,str(ROOT/'V11_k_coverage/archive.py'),'--repo',str(repo)],check=True)
    manifest=json.loads(path.read_text(encoding='utf-8'));entries={r['path']:r for r in manifest['files']};sources=[]
    for folder in ['V11_a_resident','BMMS_V11_R17_R18_R19']:sources.extend(p for p in (ROOT/folder).iterdir() if p.is_file())
    sources.extend(ROOT/p for p in ['BMMS_V11_R17_R18_R19_提交包.zip','audit_current/AUDIT_R15_R16_DELIVERY.md'])
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
    frozen=subprocess.check_output(['git','show',PREVIOUS+':BMMS/BatchMatmulMaxSum_当前审计报告_2026-09-26.md'],cwd=repo)
    assert (out/'audit_current/AUDIT_R15_R16_DELIVERY.md').read_bytes()==frozen
    manifest['scope']='V9/V10/V11 frozen history; user-selected R14 baseline; independent R17/R18 coverage rebases and R19 K256/K512 resident-A experiment, pending platform validation'
    manifest['files']=[entries[k] for k in sorted(entries)]
    for r in manifest['files']:
        assert hashlib.sha256((out/r['path']).read_bytes()).hexdigest()==r['sha256']
        assert hashlib.sha256((ROOT/r['path']).read_bytes()).hexdigest()==r['sha256']
    path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    shutil.copyfile(ROOT/'V11_a_resident/CANN_README.md',repo/'README.md')
    ignore=repo/'.gitignore';text=ignore.read_text(encoding='utf-8')
    if 'BMMS/V11_a_resident/cpu_build/' not in text:text+='BMMS/V11_a_resident/cpu_build/\n'
    ignore.write_text(text,encoding='utf-8')
    print(json.dumps({'branch':manifest['branch'],'files_verified':len(entries),'changed_prior_entries':changed},ensure_ascii=False))
if __name__=='__main__':main()

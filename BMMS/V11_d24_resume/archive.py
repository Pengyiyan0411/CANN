"""Append D24 continuation material, preserving all preceding code and packages."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1];PREVIOUS='9d289958c60e7df38df2cbbf808c23984e91a670'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);args=ap.parse_args()
    repo=args.repo.resolve();out=repo/'BMMS';manifestpath=out/'ARCHIVE_MANIFEST.json'
    manifest=json.loads(subprocess.check_output(['git','show',PREVIOUS+':BMMS/ARCHIVE_MANIFEST.json'],cwd=repo))
    entries={x['path']:x for x in manifest['files']};changed=[]
    mutable={'README.md','BatchMatmulMaxSum_当前审计报告_2026-09-26.md'}
    for rel,row in entries.items():
        p=ROOT/rel
        if sha(p)!=row['sha256']:
            assert rel in mutable,rel;changed.append(rel);shutil.copyfile(p,out/rel)
            entries[rel]={'path':rel,'bytes':p.stat().st_size,'sha256':sha(p)}
        else:assert sha(out/rel)==row['sha256'],rel
    added=[]
    for folder in ['V11_d24_resume','BMMS_V11_D24_Resume','V11_results/2026-09-27_r27_observed']:
        added.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    added.extend(ROOT/p for p in ['BMMS_V11_D24_续跑包.zip','audit_current/AUDIT_R27_DELIVERY.md'])
    for p in sorted(set(added)):
        assert p.suffix not in ['.exe','.pyc','.bin'];rel=p.relative_to(ROOT);dst=out/rel
        dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst)
        entries[rel.as_posix()]={'path':rel.as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)}
    frozen=subprocess.check_output(['git','show',PREVIOUS+':BMMS/BatchMatmulMaxSum_当前审计报告_2026-09-26.md'],cwd=repo)
    assert (out/'audit_current/AUDIT_R27_DELIVERY.md').read_bytes()==frozen
    manifest['scope']='R27 no-gain screenshot context-attributed; retain frozen R25 and resume original R23-based D24 probes; no new device code or device testing'
    manifest['files']=[entries[k] for k in sorted(entries)]
    for row in manifest['files']:
        for root in [ROOT,out]:
            p=root/row['path'];assert sha(p)==row['sha256'] and p.stat().st_size==row['bytes'],row['path']
    manifestpath.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    shutil.copyfile(ROOT/'V11_d24_resume/CANN_README.md',repo/'README.md')
    print(json.dumps({'files_verified':len(entries),'changed_old_entries':changed,'old_sources_and_packages_frozen':True},ensure_ascii=True))
if __name__=='__main__':main()

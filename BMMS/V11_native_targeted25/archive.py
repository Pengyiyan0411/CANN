"""Append R25 and D24 Native evidence; freeze every earlier source and delivery."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1];PREVIOUS='b547e58832417db9aca8e80663a0399e95e21df9'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);args=ap.parse_args()
    repo=args.repo.resolve();out=repo/'BMMS';manifestPath=out/'ARCHIVE_MANIFEST.json'
    manifest=json.loads(subprocess.check_output(['git','show',PREVIOUS+':BMMS/ARCHIVE_MANIFEST.json'],cwd=repo))
    entries={x['path']:x for x in manifest['files']};changed=[]
    mutable={'README.md','BatchMatmulMaxSum_当前审计报告_2026-09-26.md'}
    for rel,row in entries.items():
        p=ROOT/rel
        if sha(p)!=row['sha256']:
            assert rel in mutable,rel;changed.append(rel)
            dst=out/rel;shutil.copyfile(p,dst);entries[rel]={'path':rel,'bytes':p.stat().st_size,'sha256':sha(p)}
        else:assert sha(out/rel)==row['sha256'],rel
    added=[]
    for folder in ['V11_native_targeted25','BMMS_V11_R25','V11_results/2026-09-27_d24_native']:
        added.extend(p for p in (ROOT/folder).iterdir() if p.is_file())
    added.extend(ROOT/p for p in ['BMMS_V11_R25_提交包.zip','audit_current/AUDIT_D24_DELIVERY.md'])
    for p in sorted(set(added)):
        assert p.suffix not in ['.exe','.pyc','.bin'];rel=p.relative_to(ROOT);dst=out/rel
        dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst)
        entries[rel.as_posix()]={'path':rel.as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)}
    frozen=subprocess.check_output(['git','show',PREVIOUS+':BMMS/BatchMatmulMaxSum_当前审计报告_2026-09-26.md'],cwd=repo)
    assert (out/'audit_current/AUDIT_D24_DELIVERY.md').read_bytes()==frozen
    manifest['scope']='Frozen R23 baseline; D24 N01-N05 five 15/15 Pass results; R25 targeted Native K128 consumers and independent ablations; platform validation pending'
    manifest['files']=[entries[k] for k in sorted(entries)]
    for row in manifest['files']:
        for root in [ROOT,out]:
            p=root/row['path'];assert sha(p)==row['sha256'] and p.stat().st_size==row['bytes'],row['path']
    manifestPath.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    shutil.copyfile(ROOT/'V11_native_targeted25/CANN_README.md',repo/'README.md')
    ignore=repo/'.gitignore';content=ignore.read_text(encoding='utf-8')
    for folder in ['cpu_build','host_build']:
        pattern='BMMS/V11_native_targeted25/'+folder+'/'
        if pattern not in content:content+=pattern+'\n'
    ignore.write_text(content,encoding='utf-8')
    print(json.dumps({'files_verified':len(entries),'changed_old_entries':changed,'all_prior_sources_and_packs_frozen':True},ensure_ascii=False))
if __name__=='__main__':main()

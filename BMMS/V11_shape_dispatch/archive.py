"""Append R22 and compile-failure evidence; freeze all 497 prior manifest entries."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
PREVIOUS='c0a34e5828260c8311e53cec5b9dfbee8e7dab06'
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);args=ap.parse_args()
    repo=args.repo.resolve();out=repo/'BMMS';path=out/'ARCHIVE_MANIFEST.json'
    previous=json.loads(subprocess.check_output(['git','show',PREVIOUS+':BMMS/ARCHIVE_MANIFEST.json'],cwd=repo))
    subprocess.run([sys.executable,str(ROOT/'V11_native_specialize/archive.py'),'--repo',str(repo)],check=True)
    manifest=json.loads(path.read_text(encoding='utf-8'));entries={r['path']:r for r in manifest['files']};sources=[]
    for folder in ['V11_shape_dispatch','BMMS_V11_R22']:
        sources.extend(p for p in (ROOT/folder).iterdir() if p.is_file())
    sources.extend(ROOT/p for p in ['BMMS_V11_R22_提交包.zip','audit_current/AUDIT_R20_R21_DELIVERY.md'])
    sources.extend(p for p in (ROOT/'V11_results/2026-09-27_r20_compile_failed').iterdir() if p.is_file())
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
    assert (out/'audit_current/AUDIT_R20_R21_DELIVERY.md').read_bytes()==frozen
    manifest['scope']='Frozen history; R20 compile failed with no log; R14 baseline; R22 host shape-specific fixed kernels; CANN/NPU validation pending'
    manifest['files']=[entries[k] for k in sorted(entries)]
    for row in manifest['files']:
        for base in [ROOT,out]:
            p=base/row['path'];assert p.stat().st_size==row['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256']
    path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    shutil.copyfile(ROOT/'V11_shape_dispatch/CANN_README.md',repo/'README.md')
    ignore=repo/'.gitignore';content=ignore.read_text(encoding='utf-8')
    for folder in ['cpu_build','dispatch_build']:
        pattern='BMMS/V11_shape_dispatch/'+folder+'/'
        if pattern not in content:content+=pattern+'\n'
    ignore.write_text(content,encoding='utf-8')
    print(json.dumps({'branch':manifest['branch'],'files_verified':len(entries),'changed_prior_entries':changed},ensure_ascii=False))
if __name__=='__main__':main()

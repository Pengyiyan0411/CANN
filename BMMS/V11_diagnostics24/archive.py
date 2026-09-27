"""Append D24 diagnostics and confirmed R23 screenshots without rewriting old deliverables."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
PREVIOUS='9995599ae1ba5e275f49167db6b79f7337f4c6b9'
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);args=ap.parse_args()
    repo=args.repo.resolve();out=repo/'BMMS';path=out/'ARCHIVE_MANIFEST.json'
    previous=json.loads(subprocess.check_output(['git','show',PREVIOUS+':BMMS/ARCHIVE_MANIFEST.json'],cwd=repo))
    subprocess.run([sys.executable,str(ROOT/'V11_split_k/archive.py'),'--repo',str(repo)],check=True)
    manifest=json.loads(path.read_text(encoding='utf-8'));entries={r['path']:r for r in manifest['files']};sources=[]
    for folder in ['V11_diagnostics24','BMMS_V11_D24_Diagnostics','V11_results/2026-09-27_r23_submission']:
        sources.extend(p for p in (ROOT/folder).iterdir() if p.is_file())
    sources.extend(ROOT/p for p in ['BMMS_V11_D24_诊断包.zip','audit_current/AUDIT_R23_DELIVERY.md'])
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
    assert (out/'audit_current/AUDIT_R23_DELIVERY.md').read_bytes()==frozen
    manifest['scope']='Frozen history; R23 two 15/15 Pass screenshots; D24 route-specific host-only diagnostics; no new performance kernel or local CANN/NPU validation'
    manifest['files']=[entries[k] for k in sorted(entries)]
    for row in manifest['files']:
        for base in [ROOT,out]:
            p=base/row['path'];assert p.stat().st_size==row['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256']
    path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    shutil.copyfile(ROOT/'V11_diagnostics24/CANN_README.md',repo/'README.md')
    ignore=repo/'.gitignore';content=ignore.read_text(encoding='utf-8')
    for folder in ['cpu_build','host_build']:
        pattern='BMMS/V11_diagnostics24/'+folder+'/'
        if pattern not in content:content+=pattern+'\n'
    ignore.write_text(content,encoding='utf-8')
    print(json.dumps({'branch':manifest['branch'],'files_verified':len(entries),'changed_prior_entries':changed},ensure_ascii=False))
if __name__=='__main__':main()

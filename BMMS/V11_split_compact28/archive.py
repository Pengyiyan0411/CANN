"""Append R28 and L04/L06 while checking every frozen historical artifact."""
from pathlib import Path
import hashlib,json,re,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT/'CANN_archive';OUT=REPO/'BMMS'
PREVIOUS='862907825fd4e688d514752146f23a32c2cd246b'
AUDIT='BatchMatmulMaxSum_当前审计报告_2026-09-26.md'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    raw=subprocess.check_output(['git','show',PREVIOUS+':BMMS/ARCHIVE_MANIFEST.json'],cwd=REPO)
    manifest=json.loads(raw);entries={r['path']:r for r in manifest['files']};assert len(entries)==777
    changed=[]
    for rel,row in list(entries.items()):
        source=ROOT/rel
        if sha(source)!=row['sha256']:
            assert rel in {'README.md',AUDIT},rel
            shutil.copyfile(source,OUT/rel);entries[rel]=dict(path=rel,bytes=source.stat().st_size,sha256=sha(source));changed.append(rel)
        else:assert sha(OUT/rel)==row['sha256'],rel
    added=[ROOT/'audit_current/AUDIT_D24_L00_L05.md',ROOT/'BMMS_V11_R28_提交包.zip']
    prior_audit=subprocess.check_output(['git','show',PREVIOUS+':BMMS/'+AUDIT],cwd=REPO)
    assert added[0].read_bytes()==prior_audit
    for folder in ['V11_split_compact28','BMMS_V11_R28','V11_results/2026-09-27_d24_l04_l06']:
        added.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and not {'cpu_build','host_build','__pycache__'}.intersection(p.parts))
    for source in sorted(added):
        assert source.suffix not in {'.exe','.pyc','.bin'},str(source)
        rel=source.relative_to(ROOT).as_posix();assert rel not in entries,rel
        dest=OUT/rel;dest.parent.mkdir(exist_ok=True,parents=True);shutil.copyfile(source,dest)
        entries[rel]=dict(path=rel,bytes=source.stat().st_size,sha256=sha(source))
    manifest['scope']='R28 compact Split-K candidate on frozen R25; D24 L04/L06 positive evidence; actual-source CPU and host checks; no local CANN/NPU test; R25 remains measured baseline'
    manifest['files']=[entries[k] for k in sorted(entries)]
    for row in manifest['files']:
        for base in [ROOT,OUT]:
            p=base/row['path'];assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],row['path']
    (OUT/'ARCHIVE_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\r\n' if b'\r\n' in raw else '\n')
    readme=(ROOT/'README.md').read_text(encoding='utf-8');readme=re.sub(r'\]\((?!https?://)([^)]+)\)',r'](BMMS/\1)',readme)
    (REPO/'README.md').write_text(readme,encoding='utf-8',newline='\n')
    ignore=REPO/'.gitignore';data=subprocess.check_output(['git','show',PREVIOUS+':.gitignore'],cwd=REPO)
    nl=b'\r\n' if b'\r\n' in data else b'\n'
    for path in ['BMMS/V11_split_compact28/cpu_build/','BMMS/V11_split_compact28/host_build/']:
        if path.encode() not in data:data+=path.encode()+nl
    ignore.write_bytes(data)
    print(json.dumps(dict(files_verified=len(entries),new_entries=len(added),changed_old_entries=changed,old_sources_and_packages_frozen=True)))
if __name__=='__main__':main()

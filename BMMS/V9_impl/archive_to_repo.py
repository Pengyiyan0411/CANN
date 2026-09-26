"""Stage the V9 source/evidence archive in an existing CANN git checkout."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--repo',type=Path,required=True);args=parser.parse_args()
    repo=args.repo.resolve()
    if not (repo/'.git').exists():raise ValueError('Destination must already be a git checkout')
    out=repo/'BMMS';out.mkdir(exist_ok=True)
    selected=[ROOT/'cann.md',ROOT/'BatchMatmulMaxSum_V9_冲榜路线设计.md',ROOT/'BMMS_V9_提交实验包.zip',
              ROOT/'next_stage/C00_P01_CONTROL.asc',ROOT/'next_stage/cpu_shim.hpp']
    for name in ['D03','D04']:
        pack=ROOT/f'BMMS_V9_{name}_提交包.zip'
        if pack.exists():selected.append(pack)
    for folder in ['V9_impl','V9_design']:
        selected += [p for p in (ROOT/folder).iterdir() if p.is_file() and p.suffix in {'.asc','.cpp','.hpp','.py','.md','.json','.jsonl','.txt','.diff'}
                     and not p.name.endswith('_extracted.hpp')]
    selected += [p for p in (ROOT/'BMMS_V9_SubmitPack').iterdir() if p.is_file()]
    for name in ['D03','D04']:
        folder=ROOT/f'BMMS_V9_{name}'
        if folder.exists():selected += [p for p in folder.iterdir() if p.is_file()]
    selected += [p for p in (ROOT/'V9_results').rglob('*') if p.is_file()]
    copied=[]
    for src in sorted(set(selected)):
        relative=src.relative_to(ROOT);dst=out/relative
        dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
        copied.append({'path':relative.as_posix(),'bytes':src.stat().st_size,
                       'sha256':hashlib.sha256(src.read_bytes()).hexdigest()})
        assert src.read_bytes()==dst.read_bytes()
    info={'repository':'https://github.com/Pengyiyan0411/CANN','branch':'v9',
          'scope':'V9 single-file candidates, P01 control, reproducible offline checks, user-labelled platform evidence',
          'platform_source_identity':'user-labelled filenames; no platform source digest provided',
          'excluded':'compiler binaries, caches, external CATLASS checkout, unrelated historical versions',
          'files':copied}
    (out/'ARCHIVE_MANIFEST.json').write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'destination':str(out),'files':len(copied),'bytes':sum(p['bytes'] for p in copied)},ensure_ascii=False))


if __name__=='__main__':main()

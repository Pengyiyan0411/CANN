"""Reproducible source-extracted CPU checks. No NPU invocation."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent


def call(argv,stem,allowed=(0,)):
    p=subprocess.run(argv,cwd=HERE,capture_output=True,text=True,timeout=180)
    (HERE/(stem+'.stdout.txt')).write_text(p.stdout,encoding='utf-8')
    (HERE/(stem+'.stderr.txt')).write_text(p.stderr,encoding='utf-8')
    if p.returncode not in allowed:
        raise RuntimeError(f'{stem}: exit {p.returncode}: {p.stderr[-3000:]}')
    return p


def main():
    call([sys.executable,'prepare_cpu.py'],'prepare_cpu')
    compiler=shutil.which(os.environ.get('CXX','g++'))
    if not compiler:raise RuntimeError('C++ compiler unavailable')
    report={'device_test':False,'cann_compiled':False,
            'compiler':call([compiler,'--version'],'compiler').stdout.splitlines()[0],
            'scope':'Real extracted C++ against explicit CPU memory/layout/event-credit models; not a hardware simulator.',
            'runs':{}}
    for block in (128,64):
        exe=HERE/f'check_k{block}{".exe" if os.name=="nt" else ""}'
        cmd=[compiler,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-pthread',f'-DBMMS9D_K_BLOCK={block}']
        if block==64:cmd+=['-DBMMS9_SKIP_SPLIT=1']
        call(cmd+['source_checks.cpp','-o',str(exe)],f'k{block}_compile')
        p=call([str(exe)],f'k{block}_run',allowed=(0,2))
        report['runs'][str(block)]=json.loads(p.stdout)
        report['runs'][str(block)]['exit_code']=p.returncode
    report['source_manifest']=json.loads((HERE/'source_manifest.json').read_text(encoding='utf-8'))
    report['harness_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in
                            [HERE/'source_checks.cpp',HERE/'cube_model.hpp',HERE/'cpu_shim.hpp',HERE/'prepare_cpu.py']}
    (HERE/'cpu_checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report['runs'],indent=2))
    return 2 if any(x['strict_misses'] for x in report['runs'].values()) else 0


if __name__=='__main__':sys.exit(main())

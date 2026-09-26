"""Reproducible CPU source checks; never reports a device/performance pass."""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
BUILD=HERE/'cpu_build'
OUT=ROOT/'BMMS_V10_SubmitPack'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def call(args, name, timeout=180):
    result=subprocess.run(args,cwd=BUILD,text=True,capture_output=True,timeout=timeout)
    (BUILD/(name+'.stdout.txt')).write_text(result.stdout,encoding='utf-8')
    (BUILD/(name+'.stderr.txt')).write_text(result.stderr,encoding='utf-8')
    if result.returncode: raise RuntimeError(f'{name}: {result.returncode}: {result.stderr[-3500:]}')
    return result

def once(s,a,b):
    assert s.count(a)==1,a
    return s.replace(a,b,1)

def main():
    BUILD.mkdir(exist_ok=True)
    shim=(ROOT/'next_stage/cpu_shim.hpp').read_text(encoding='utf-8')
    # Invalidate all unused C bytes for each result, so stale tail reads fail.
    shim=once(shim,'        auto [mt,nt]=coords[current];int m0=mt*td.baseM,n0=nt*td.baseN;',
        '''        Mock::need(rm<=td.baseM,"more than one M base tile");
        std::fill(c.b->init.begin()+c.offset,c.b->init.end(),0);
        auto [mt,nt]=coords[current];int m0=mt*td.baseM,n0=nt*td.baseN;''')
    # Enforce hardware row-address alignment in the repeated Max adapter too.
    shim=once(shim,'    Mock::need(mask>=1&&mask<=64&&repeats<=255,"bad vector mask/repeats");',
        '    aligned(d);aligned(a);aligned(b);\n    Mock::need(mask>=1&&mask<=64&&repeats>=1&&repeats<=255,"bad vector mask/repeats");')
    (BUILD/'cpu_shim.hpp').write_text(shim,encoding='utf-8')
    compiler=shutil.which('g++') or r'C:\msys64\ucrt64\bin\g++.exe'
    os.environ['PATH']=str(Path(compiler).parent)+os.pathsep+os.environ['PATH']
    compiler_version=call([compiler,'--version'],'compiler').stdout.splitlines()[0]
    manifest=json.loads((OUT/'MANIFEST.json').read_text(encoding='utf-8'))
    report={'scope':'source-extracted CPU semantics, bounds, ownership and planning',
        'compiler':compiler_version,'cann_compiled':False,'npu_tested':False,
        'full_domain_precision_accepted':False,'runs':{}}
    outputs={}
    for item in manifest['variants']:
        path=OUT/item['file'];assert sha(path)==item['sha256']
        src=path.read_text(encoding='utf-8')
        defines='\n'.join(re.findall(r'^#define BMMS10_(?:SPLIT_N|TILE_M|TILE_N) .*$',src,re.M))
        extracted=defines+'\n'+src.split('// BMMS10_CPU_BEGIN\n',1)[1].split('// BMMS10_CPU_END',1)[0]
        (BUILD/'candidate.hpp').write_text(extracted,encoding='utf-8')
        name=item['variant'];exe=BUILD/(name+'.exe')
        call([compiler,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-pthread',
            '-I',str(BUILD),str(HERE/'source_checks.cpp'),'-o',str(exe)],name+'_compile')
        run=call([str(exe)],name+'_run',timeout=240)
        result=json.loads(run.stdout)
        outputs[name]=result.pop('output_bits')
        result['output_bits_sha256']=hashlib.sha256(json.dumps(outputs[name],sort_keys=True).encode()).hexdigest()
        result['source_sha256']=sha(path)
        report['runs'][name]=result
        print(json.dumps({'variant':name,**result},ensure_ascii=False),flush=True)
    # F01 and F02 have different Sum trees when N is split, so require numerical
    # oracle agreement above; report bit differences without asserting equality.
    left,right=outputs.values()
    report['cross_variant_bitwise_different_cases']=sum(left[k]!=right[k] for k in left)
    report['artifacts']={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in
        [HERE/'source_checks.cpp',HERE/'run_checks.py',ROOT/'next_stage/cpu_shim.hpp']}
    (HERE/'CHECKS.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    shutil.copyfile(HERE/'CHECKS.json',OUT/'CPU_CHECKS.json')

if __name__=='__main__': main()

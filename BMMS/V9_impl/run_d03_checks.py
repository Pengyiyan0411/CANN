"""Compare frozen D01 and D03 in the same source-extracted CPU harness."""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
BUILD=HERE/'d03_cpu'


def call(argv,stem):
    p=subprocess.run(argv,cwd=BUILD,capture_output=True,text=True,timeout=180)
    (BUILD/(stem+'.stdout.txt')).write_text(p.stdout,encoding='utf-8')
    (BUILD/(stem+'.stderr.txt')).write_text(p.stderr,encoding='utf-8')
    if p.returncode:raise RuntimeError(f'{stem}: exit {p.returncode}: {p.stderr[-2500:]}')
    return p


def main():
    BUILD.mkdir(exist_ok=True)
    call([sys.executable,str(HERE/'prepare_cpu.py')],'prepare_common')
    harness=(HERE/'source_checks.cpp').read_text(encoding='utf-8')
    harness=harness.replace('#include "cube_model.hpp"','#include "../cube_model.hpp"')
    harness=harness.replace('#include "common_extracted.hpp"','#include "../common_extracted.hpp"')
    anchor='    std::cout<<std::setprecision(12)'
    assert harness.count(anchor)==1
    extra='''    // Repeated C-slot reuse across tails and task boundaries, including
    // exactly two/three tiles and workers with an odd number of output tiles.
    for(int rev=0;rev<2;++rev)for(int pattern=0;pattern<2;++pattern){
        for(auto dims:std::vector<std::array<int,5>>{
            {1,16,256,256,1},{1,16,384,288,1},
            {1,80,272,288,1},{5,16,16,352,2}}){
            auto [B,M,N,K,c]=dims;
            dense<half,false,false>(B,M,N,K,c,pattern,rev);
            dense<bfloat16_t,true,true>(B,M,N,K,c,pattern,rev);
        }
    }
    uint64_t digest=14695981039346656037ULL;
    for(const auto& [key,bits]:outputs){
        for(unsigned char ch:key){digest^=ch;digest*=1099511628211ULL;}
        for(uint32_t word:bits){digest^=word;digest*=1099511628211ULL;}
    }
    std::cout<<"{\\\"output_digest\\\":\\\""<<digest<<"\\\"}\\n";
'''
    harness=harness.replace(anchor,extra+anchor,1)
    (BUILD/'source_checks.cpp').write_text(harness,encoding='utf-8')
    compiler=shutil.which(os.environ.get('CXX','g++'))
    if not compiler:raise RuntimeError('g++ is required')
    results={}
    for name,file in [('D01','dense_fragment.asc'),('D03','dense_c2_fragment.asc')]:
        source=(HERE/file).read_text(encoding='utf-8')
        extracted=source.split('// BMMS9_CPU_EXTRACT_END',1)[0]
        depth=0
        for line in extracted.splitlines():
            if re.match(r'\s*#\s*(if|ifdef|ifndef)\b',line):depth+=1
            elif re.match(r'\s*#\s*endif\b',line):depth-=1
        assert depth>=0
        extracted+='\n'+'#endif\n'*depth
        (BUILD/'dense_extracted.hpp').write_text(extracted,encoding='utf-8')
        exe=BUILD/(name+('.exe' if os.name=='nt' else ''))
        call([compiler,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-pthread',
              '-DBMMS9D_K_BLOCK=128','-DBMMS9_SKIP_SPLIT=1','source_checks.cpp','-o',str(exe)],name+'_compile')
        p=call([str(exe)],name+'_run')
        rows=p.stdout.strip().splitlines();assert len(rows)==2
        results[name]={**json.loads(rows[1]),**json.loads(rows[0]),
                       'fragment_sha256':hashlib.sha256((HERE/file).read_bytes()).hexdigest()}
        assert results[name]['strict_misses']==results[name]['combined_misses']==0
        print(name+': '+json.dumps(results[name]),flush=True)
    assert results['D01']['output_digest']==results['D03']['output_digest']
    report={'scope':'Explicit CPU layout, arithmetic, bounds, ownership and event-credit model; not CANN or hardware',
            'cann_compiled':False,'npu_tested':False,'bounded_test_results_bitwise_equal':True,
            'known_precision_counterexamples_remain':True,'runs':results,
            'harness_sha256':hashlib.sha256(harness.encode()).hexdigest(),
            'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (HERE/'d03_checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    (HERE.parent/'BMMS_V9_D03/CPU_CHECKS.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('D01/D03 bounded CPU outputs match bitwise; no NPU result claimed.',flush=True)


if __name__=='__main__':main()

"""Source CPU checks plus logical-transfer counters; not hardware profiling."""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
BUILD=HERE/'d04_cpu'


def call(argv,stem):
    p=subprocess.run(argv,cwd=BUILD,capture_output=True,text=True,timeout=180)
    (BUILD/(stem+'.stdout.txt')).write_text(p.stdout,encoding='utf-8')
    (BUILD/(stem+'.stderr.txt')).write_text(p.stderr,encoding='utf-8')
    if p.returncode:raise RuntimeError(f'{stem}: {p.returncode}: {p.stderr[-2500:]}')
    return p


def once(s,a,b):
    assert s.count(a)==1,a
    return s.replace(a,b,1)


def extract(source):
    part=source.split('// BMMS9_CPU_EXTRACT_END',1)[0];depth=0
    for line in part.splitlines():
        if re.match(r'\s*#\s*(if|ifdef|ifndef)\b',line):depth+=1
        elif re.match(r'\s*#\s*endif\b',line):depth-=1
    assert depth>=0
    return part+'\n'+'#endif\n'*depth


def main():
    BUILD.mkdir(exist_ok=True)
    call([sys.executable,str(HERE/'prepare_cpu.py')],'prepare_common')
    shim=(HERE/'cpu_shim.hpp').read_text(encoding='utf-8')
    shim=once(shim,'constexpr int PIPE_V=0, PIPE_ALL=1, PIPE_MTE2=2, PIPE_MTE3=3, PIPE_FIX=4;',
              'constexpr int PIPE_V=0, PIPE_ALL=1, PIPE_MTE2=2, PIPE_MTE3=3, PIPE_FIX=4, PIPE_M=5;')
    shim=once(shim,'inline thread_local bool deferred=true;',
              'inline thread_local bool deferred=true;\ninline thread_local bool smallMmadPending=false;\ninline std::atomic<uint64_t> pipeMBarriers{0};')
    shim=once(shim,'template<int P>void PipeBarrier(){}',
              'template<int P>void PipeBarrier(){if constexpr(P==PIPE_M){++Mock::pipeMBarriers;Mock::smallMmadPending=false;}}')
    (BUILD/'cpu_shim.hpp').write_text(shim,encoding='utf-8')
    model=(HERE/'cube_model.hpp').read_text(encoding='utf-8')
    model=once(model,'enum class QuantMode_t { NoQuant };',
        'namespace Traffic {inline std::atomic<uint64_t> gmInputBytes{0},publishes{0},cWriteBytes{0},smallMmads{0};}\nenum class QuantMode_t { NoQuant };')
    model=once(model,'    for(int r=0;r<p.nValue;++r)',
               '    Traffic::gmInputBytes+=uint64_t(p.nValue)*p.dValue*sizeof(T);\n    for(int r=0;r<p.nValue;++r)')
    model=once(model,'    Mock::need(p.m%16==0&&p.n%16==0&&p.k%16==0,"unaligned Mmad model dimensions");',
        '''    Mock::need(p.m%16==0&&p.n%16==0&&p.k%16==0,"unaligned Mmad model dimensions");
#ifdef BMMS9_ENFORCE_SMALL_M
    Mock::need(!Mock::smallMmadPending,"previous small-tile MMAD lacks PIPE_M barrier");
#endif
    if((p.m/16)*(p.n/16)<10){++Traffic::smallMmads;Mock::smallMmadPending=true;}
''')
    model=once(model,'    Mock::need(p.ndNum==1&&p.srcStride>=p.mSize&&p.dstStride>=p.nSize,"invalid Fixpipe model strides");',
               '    ++Traffic::publishes;Traffic::cWriteBytes+=uint64_t(p.mSize)*p.nSize*sizeof(D);\n    Mock::need(p.ndNum==1&&p.srcStride>=p.mSize&&p.dstStride>=p.nSize,"invalid Fixpipe model strides");')
    (BUILD/'cube_model.hpp').write_text(model,encoding='utf-8')
    template=(HERE/'source_checks.cpp').read_text(encoding='utf-8')
    template=template.replace('#include "common_extracted.hpp"','#include "../common_extracted.hpp"')
    template=template.replace('#include <iostream>','#include <iostream>\n#include <fstream>')
    template=once(template,'                fn(w);','''                fn(w);
#ifdef BMMS9_ENFORCE_SMALL_M
                Mock::need(!Mock::smallMmadPending,"undrained small-tile MMAD dependency");
#endif''')
    extra=r'''    for(int rev=0;rev<2;++rev)for(int pattern=0;pattern<2;++pattern){
        for(auto dims:std::vector<std::array<int,5>>{
            {1,128,128,256,1},{1,144,272,288,1},{1,240,144,320,2},
            {1,272,528,352,2},{3,144,144,256,4},{1,16,512,320,3}}){
            auto [B,M,N,K,c]=dims;
            dense<half,false,false>(B,M,N,K,c,pattern,rev);
            dense<bfloat16_t,true,true>(B,M,N,K,c,pattern,rev);
            if(M==128){
                dense<half,false,true>(B,M,N,K,c,pattern,rev);
                dense<half,true,false>(B,M,N,K,c,pattern,rev);
                dense<half,true,true>(B,M,N,K,c,pattern,rev);
                dense<bfloat16_t,false,false>(B,M,N,K,c,pattern,rev);
                dense<bfloat16_t,false,true>(B,M,N,K,c,pattern,rev);
                dense<bfloat16_t,true,false>(B,M,N,K,c,pattern,rev);
            }
        }
    }
    for(int rev=0;rev<2;++rev)dense<half,false,false>(1,8192,16,256,2,0,rev);
    const uint64_t barriers=Mock::pipeMBarriers.load(),small=Traffic::smallMmads.load();
#ifdef BMMS9_ENFORCE_SMALL_M
    Mock::need(barriers==small&&small>0,"small-tile barrier count mismatch");
#endif
    Traffic::gmInputBytes=0;Traffic::publishes=0;Traffic::cWriteBytes=0;
    dense<half,false,false>(1,256,256,256,1,0,false);
    std::ofstream bitsFile("output_bits.json");bitsFile<<"{";bool first=true;
    for(const auto& [key,bits]:outputs){
        if(!first)bitsFile<<",";first=false;bitsFile<<"\""<<key<<"\":[";
        for(size_t i=0;i<bits.size();++i){if(i)bitsFile<<",";bitsFile<<bits[i];}bitsFile<<"]";
    }
    bitsFile<<"}\n";bitsFile.close();
    std::cout<<"{\"logical_input_bytes_fixture\":"<<Traffic::gmInputBytes.load()
        <<",\"tile_publishes_fixture\":"<<Traffic::publishes.load()
        <<",\"c_write_bytes_fixture\":"<<Traffic::cWriteBytes.load()
        <<",\"small_mmads_checked\":"<<small<<",\"pipe_m_barriers\":"<<barriers<<"}\n";
'''
    template=once(template,'    std::cout<<std::setprecision(12)',extra+'    std::cout<<std::setprecision(12)')
    compiler=shutil.which(os.environ.get('CXX','g++'))
    if not compiler:raise RuntimeError('g++ is required')
    reports={};output_records={}
    for name,file in [('D03','dense_c2_fragment.asc'),('D04','dense_m128_fragment.asc')]:
        source=(HERE/file).read_text(encoding='utf-8')
        (BUILD/'dense_extracted.hpp').write_text(extract(source),encoding='utf-8')
        harness=template
        if name=='D04':
            harness=harness.replace('bmms9d::','bmms9r::').replace('bmms83::SmallKConsumer','bmms9r::RowMaxConsumer')
        (BUILD/'source_checks.cpp').write_text(harness,encoding='utf-8')
        exe=BUILD/(name+('.exe' if os.name=='nt' else ''))
        cmd=[compiler,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-pthread','-DBMMS9_SKIP_SPLIT=1']
        if name=='D04':cmd+=['-DBMMS9_ENFORCE_SMALL_M=1']
        call(cmd+['source_checks.cpp','-o',str(exe)],name+'_compile')
        rows=call([str(exe)],name+'_run').stdout.strip().splitlines();assert len(rows)==2
        reports[name]={**json.loads(rows[1]),**json.loads(rows[0]),
                       'fragment_sha256':hashlib.sha256((HERE/file).read_bytes()).hexdigest()}
        assert reports[name]['strict_misses']==reports[name]['combined_misses']==0
        output_records[name]=json.loads((BUILD/'output_bits.json').read_text(encoding='utf-8'))
        shutil.copyfile(BUILD/'output_bits.json',BUILD/(name+'_output_bits.json'))
        reports[name]['output_bits_sha256']=hashlib.sha256((BUILD/'output_bits.json').read_bytes()).hexdigest()
        print(name+': '+json.dumps(reports[name]),flush=True)
    assert output_records['D03']==output_records['D04']
    assert reports['D03']['logical_input_bytes_fixture']==786432
    assert reports['D04']['logical_input_bytes_fixture']==524288
    assert reports['D03']['tile_publishes_fixture']==8 and reports['D04']['tile_publishes_fixture']==4
    assert reports['D03']['c_write_bytes_fixture']==reports['D04']['c_write_bytes_fixture']==262144
    report={'scope':'Source-extracted CPU arithmetic/storage/event model and logical API transfer counters; no device timing',
            'cann_compiled':False,'npu_tested':False,'bounded_output_records_compared_bitwise':True,
            'known_precision_counterexamples_remain':True,'traffic_fixture':{'B':1,'M':256,'N':256,'K':256,'cores':1},
            'runs':reports,'generated_harness_sha256':hashlib.sha256(template.encode()).hexdigest(),
            'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    for path in [HERE/'d04_checks.json',HERE.parent/'BMMS_V9_D04/CPU_CHECKS.json']:
        path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('D03/D04 exact output records match; logical input bytes reduced 1/3 for the named fixture.',flush=True)


if __name__=='__main__':main()

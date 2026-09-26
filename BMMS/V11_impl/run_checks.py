"""Execute actual R01 device source in a bounded CPU layout/event model.

No CANN/NPU claim. D01 is executed on an identical traffic fixture only.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from build import BASE, OUT, ROOT, HERE, once, sha

BUILD=HERE/'cpu_build'
V9=ROOT/'V9_impl'

def call(argv,stem,timeout=300):
    p=subprocess.run(argv,cwd=BUILD,capture_output=True,text=True,timeout=timeout)
    (BUILD/(stem+'.stdout.txt')).write_text(p.stdout,encoding='utf-8')
    (BUILD/(stem+'.stderr.txt')).write_text(p.stderr,encoding='utf-8')
    if p.returncode:raise RuntimeError(f'{stem}: {p.returncode}: {p.stderr[-3000:]}')
    return p.stdout

def extract(s,marker):
    p=s.split(marker,1)[0];depth=0
    for line in p.splitlines():
        if re.match(r'\s*#\s*(if|ifdef|ifndef)\b',line):depth+=1
        elif re.match(r'\s*#\s*endif\b',line):depth-=1
    assert depth>=0
    return p+'\n'+'#endif\n'*depth

def prepare():
    BUILD.mkdir(exist_ok=True)
    spec=importlib.util.spec_from_file_location('prepare_v9',V9/'prepare_cpu.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    mod.HERE=BUILD;mod.make_shim()
    shim=(BUILD/'cpu_shim.hpp').read_text(encoding='utf-8')
    shim=once(shim,'constexpr int PIPE_V=0, PIPE_ALL=1, PIPE_MTE2=2, PIPE_MTE3=3, PIPE_FIX=4;',
        'constexpr int PIPE_V=0, PIPE_ALL=1, PIPE_MTE2=2, PIPE_MTE3=3, PIPE_FIX=4, PIPE_M=5;')
    shim=once(shim,'inline thread_local bool deferred=true;',
        'inline thread_local bool deferred=true;\ninline thread_local bool smallMmadPending=false;\ninline std::atomic<uint64_t> pipeMBarriers{0};')
    shim=once(shim,'template<int P>void PipeBarrier(){}',
        'template<int P>void PipeBarrier(){if constexpr(P==PIPE_M){++Mock::pipeMBarriers;Mock::smallMmadPending=false;}}')
    (BUILD/'cpu_shim.hpp').write_text(shim,encoding='utf-8')
    s=BASE.read_text(encoding='utf-8');between=mod.between
    common='#pragma once\nnamespace bmmmaxsum_v43 {constexpr float NEG_INF=-__builtin_inff();}\n'
    common+=between(s,'namespace bmms71 {','// BMMS71_VECTOR_MODULE_END')
    common+='\nnamespace bmms8 {inline int CeilDivI(int x,int y){return (x+y-1)/y;}\n'
    common+=between(s,'__aicore__ inline void PairAccumulate(', 'template<class T,bool SUM_ROWS>\n__aicore__ inline void LaneSkinnyDevice')+'}\n'
    common+=between(s,'namespace bmms83 {','// Only fixed-size TBuf allocations occur on the AIC side.')
    common+=between(s,'class SmallKConsumer {','template<class T,bool TA,bool TB,int TK>\n__aicore__ inline void NativeEntry')+'}\n'
    (BUILD/'common_extracted.hpp').write_text(common,encoding='utf-8')
    model=(V9/'cube_model.hpp').read_text(encoding='utf-8')
    model=once(model,'enum class QuantMode_t { NoQuant };',
        '''namespace Traffic {
inline std::atomic<uint64_t> gmInputBytes{0},gmCopies{0},l0Bytes{0},l0Copies{0},mmads{0},publishes{0},cWriteBytes{0};
inline void reset(){gmInputBytes=0;gmCopies=0;l0Bytes=0;l0Copies=0;mmads=0;publishes=0;cWriteBytes=0;}
}
enum class QuantMode_t { NoQuant };''')
    model=once(model,'    for(int r=0;r<p.nValue;++r)',
        '    Traffic::gmInputBytes+=uint64_t(p.nValue)*p.dValue*sizeof(T);++Traffic::gmCopies;\n    for(int r=0;r<p.nValue;++r)')
    model=once(model,'    for(int block=0;block<p.repeatTimes;++block)',
        '    Traffic::l0Bytes+=uint64_t(p.repeatTimes)*256*sizeof(T);++Traffic::l0Copies;\n    for(int block=0;block<p.repeatTimes;++block)')
    model=once(model,'    Mock::need(p.m%16==0&&p.n%16==0&&p.k%16==0,"unaligned Mmad model dimensions");',
        '''    Mock::need(p.m%16==0&&p.n%16==0&&p.k%16==0,"unaligned Mmad model dimensions");++Traffic::mmads;
#ifdef CHECK_R01
    Mock::need(!Mock::smallMmadPending,"small MMAD missing PIPE_M dependency");
    if((p.m/16)*(p.n/16)<10)Mock::smallMmadPending=true;
#endif''')
    model=once(model,'    for(int m=0;m<p.mSize;++m)',
        '    ++Traffic::publishes;Traffic::cWriteBytes+=uint64_t(p.mSize)*p.nSize*sizeof(D);\n    for(int m=0;m<p.mSize;++m)')
    (BUILD/'cube_model.hpp').write_text(model,encoding='utf-8')
    real=(OUT/'R01_REUSE_2X2.asc').read_text(encoding='utf-8')
    fragment=(HERE/'reuse_fragment.asc').read_text(encoding='utf-8')
    assert real.count(fragment)==1
    (BUILD/'reuse_extracted.hpp').write_text(extract(fragment,'// BMMS11_CPU_EXTRACT_END'),encoding='utf-8')
    old=(V9/'dense_fragment.asc').read_text(encoding='utf-8')
    assert old in (ROOT/'BMMS_V9_SubmitPack/D01_DENSE_K128.asc').read_text(encoding='utf-8')
    (BUILD/'dense_extracted.hpp').write_text(extract(old,'// BMMS9_CPU_EXTRACT_END'),encoding='utf-8')

def harness():
    s=(V9/'source_checks.cpp').read_text(encoding='utf-8')
    # Reuse the independently checked CPU worker/FP64 oracle infrastructure.
    s=s[:s.index('#ifndef BMMS9_SKIP_SPLIT\ntemplate<class T>')]
    s=s.replace('#if __has_include("splitk_extracted.hpp")\n#include "splitk_extracted.hpp"\n#endif',
        '#include "reuse_extracted.hpp"\n#include <fstream>')
    s=s.replace('#define BMMS9_CPU_TEST 1','#define BMMS9_CPU_TEST 1\n#define BMMS11_CPU_TEST 1')
    s=s.replace('bmms9d::','TEST_NS::').replace('bmms83::SmallKConsumer','TEST_CONSUMER').replace('TEST_NS::StagedProducer','TEST_PRODUCER')
    s=once(s,'int denseRuns=0,splitRuns=0;','int denseRuns=0,splitRuns=0,knownLimits=0;')
    s=once(s,'                fn(w);','''                fn(w);
#ifdef CHECK_R01
                Mock::need(!Mock::smallMmadPending,"small MMAD dependency not drained");
#endif''')
    needle='    std::vector<double>gold(B,0);'
    custom='''    if(pattern>=2){
        for(auto&v:a)v=T(0);for(auto&v:b)v=T(0);
        for(int z=0;z<B;++z){
            for(int m=0;m<M;++m){
                if(pattern==4){a[ai(z,m,0)]=T(m%2?-64.f:64.f);if(m%2==0)a[ai(z,m,1)]=T(0.015625f);}
                if(pattern==5)for(int k=0;k<2;++k)a[ai(z,m,k)]=T(std::ldexp(1.f,64));
            }
            for(int n=0;n<N;++n){
                if(pattern==4){b[bi(z,0,n)]=T(64.f);b[bi(z,1,n)]=T(0.0078125f);}
                if(pattern==5){b[bi(z,0,n)]=T(std::ldexp(1.f,64));b[bi(z,1,n)]=T(-std::ldexp(1.f,64));}
            }
        }
    }
    const auto aBefore=a,bBefore=b;
'''
    s=once(s,needle,custom+needle)
    s=once(s,'        flags.drained();assess(key,y,gold);++denseRuns;',
        '''        flags.drained();
        Mock::need(std::memcmp(a.data(),aBefore.data(),a.size()*sizeof(T))==0,"A mutated");
        Mock::need(std::memcmp(b.data(),bBefore.data(),b.size()*sizeof(T))==0,"B mutated");
        if(pattern>=4){
            bool fail=false;
            for(int z=0;z<B;++z){double ref=float(gold[z]),err=std::abs(double(y[z])-ref);
                double rel=ref==0?(err==0?0:INFINITY):err/std::abs(ref);
                if(!std::isfinite(y[z])||!(err<1e-4&&rel<1e-4))fail=true;}
            Mock::need(fail,"known numerical limitation unexpectedly disappeared");++knownLimits;return;
        }
        assess(key,y,gold);++denseRuns;''')
    return s+(HERE/'checks_tail.cpp').read_text(encoding='utf-8')

def main():
    prepare();s=harness();(BUILD/'source_checks.cpp').write_text(s,encoding='utf-8')
    compiler=shutil.which(os.environ.get('CXX','g++'))
    if not compiler:raise RuntimeError('g++ required')
    versions={'R01':['-DCHECK_R01=1','-DTEST_NS=bmms11','-DTEST_PRODUCER=bmms11::ReuseProducer','-DTEST_CONSUMER=bmms11::RowMaxConsumer'],
              'D01':['-DTEST_NS=bmms9d','-DTEST_PRODUCER=bmms9d::StagedProducer','-DTEST_CONSUMER=bmms83::SmallKConsumer']}
    reports={}
    for name,defs in versions.items():
        exe=BUILD/(name+('.exe' if os.name=='nt' else ''))
        call([compiler,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-pthread',*defs,'source_checks.cpp','-o',str(exe)],name+'_compile')
        reports[name]=json.loads(call([str(exe)],name+'_run'))
        (HERE/(name+'_CPU_RESULT.json')).write_text(json.dumps(reports[name],indent=2)+'\n',encoding='utf-8')
        print(name+': '+json.dumps({k:v for k,v in reports[name].items() if k!='output_bits'}),flush=True)
    r,d=reports['R01']['traffic_fixture'],reports['D01']['traffic_fixture']
    assert r['gm_bytes']==196608 and d['gm_bytes']==393216
    assert r['gm_calls']==2 and d['gm_calls']==16
    assert r['l0_bytes']==196608 and d['l0_bytes']==393216
    assert r['c_write_bytes']==d['c_write_bytes']==131072
    assert r['publishes']==d['publishes']==4
    for key,v in reports['D01']['output_bits'].items():assert reports['R01']['output_bits'][key]==v
    manifest=json.loads((OUT/'MANIFEST.json').read_text(encoding='utf-8'))
    checks={'source_sha256':sha(OUT/manifest['file']),'scope':'actual source CPU layout/arithmetic/event model; not NPU simulation',
        'cann_compiled':False,'npu_tested':False,'full_domain_precision_accepted':False,
        'fixture':{'B':1,'M':128,'N':256,'K':256,'cores':1},'fixture_outputs_match_bitwise':True,
        'runs':{k:{kk:vv for kk,vv in v.items() if kk!='output_bits'} for k,v in reports.items()},
        'artifacts':{str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in
            [HERE/'reuse_fragment.asc.in',HERE/'reuse_fragment.asc',HERE/'build.py',Path(__file__),HERE/'checks_tail.cpp',
             V9/'prepare_cpu.py',V9/'source_checks.cpp',V9/'cube_model.hpp',ROOT/'next_stage/cpu_shim.hpp',BASE]}}
    for p in [HERE/'CHECKS.json',OUT/'CPU_CHECKS.json']:
        p.write_text(json.dumps(checks,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()

"""Check both real-source descendants, ring ownership, routes and a negative control."""
from pathlib import Path
import importlib.util
import json
import os
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
OUT=ROOT/'BMMS_V11_R02_R03'
BUILD=HERE/'cpu_build'

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m

# The old check runner imports its sibling `build`; explicitly bind that module.
base_build=load('build',ROOT/'V11_impl/build.py')
parent=load('r01_checks',ROOT/'V11_impl/run_checks.py')
parent.BUILD=BUILD
once=base_build.once;sha=base_build.sha

def call(argv,stem,expect_failure=False):
    p=subprocess.run(argv,cwd=BUILD,capture_output=True,text=True,timeout=300)
    (BUILD/(stem+'.stdout.txt')).write_text(p.stdout,encoding='utf-8',newline='\n')
    (BUILD/(stem+'.stderr.txt')).write_text(p.stderr,encoding='utf-8',newline='\n')
    if expect_failure:
        assert p.returncode!=0 and 'ring freed before all published data was read' in p.stderr,p.stderr
    elif p.returncode:raise RuntimeError(f'{stem}: {p.returncode}: {p.stderr[-3000:]}')
    return p

def prepare():
    parent.prepare()
    shim=(BUILD/'cpu_shim.hpp').read_text(encoding='utf-8')
    audit=(HERE/'ring_audit.hpp').read_text(encoding='utf-8')
    shim=once(shim,'namespace AscendC {',audit+'\nnamespace AscendC {') if shim.count('namespace AscendC {')==1 else shim.replace('namespace AscendC {',audit+'\nnamespace AscendC {',1)
    needle='template<class T>void DataCopyPad(LocalTensor<T>d,GlobalTensor<T>s,DataCopyExtParams cp,DataCopyPadExtParams<T> pad){'
    shim=once(shim,needle,needle+'\n    RingAudit::read(s.p,uint64_t(cp.blockCount)*cp.blockLen/sizeof(T));')
    needle='template<int MODE,int PIPE>void CrossCoreSetFlag(uint16_t id){'
    shim=once(shim,needle,needle+'if constexpr(MODE==2)RingAudit::signal(id);')
    (BUILD/'cpu_shim.hpp').write_text(shim,encoding='utf-8',newline='\n')
    model=(BUILD/'cube_model.hpp').read_text(encoding='utf-8')
    needle='template<class D,class S>void Fixpipe(GlobalTensor<D>d,LocalTensor<S>s,FixpipeParamsV220 p){'
    model=once(model,needle,needle+'\n    RingAudit::write(d.p,uint64_t(p.mSize)*p.nSize);')
    (BUILD/'cube_model.hpp').write_text(model,encoding='utf-8',newline='\n')
    for filename,target,marker in [('macro_ring_fragment.asc','ring_extracted.hpp','// BMMS11R2_CPU_EXTRACT_END'),
                                   ('residual_dense_fragment.asc','residual_extracted.hpp','// BMMS9_CPU_EXTRACT_END')]:
        fragment=(HERE/filename).read_text(encoding='utf-8')
        candidate='R02_MACRO_RING.asc' if filename.startswith('macro') else 'R03_RESIDUAL_DENSE.asc'
        assert fragment in (OUT/candidate).read_text(encoding='utf-8')
        (BUILD/target).write_text(parent.extract(fragment,marker),encoding='utf-8',newline='\n')

def harness():
    s=parent.harness()
    s=once(s,'#define BMMS11_CPU_TEST 1','#define BMMS11_CPU_TEST 1\n#define BMMS11R2_CPU_TEST 1')
    s=once(s,'#include "reuse_extracted.hpp"','#include "reuse_extracted.hpp"\n#include "ring_extracted.hpp"\n#include "residual_extracted.hpp"')
    s=once(s,'int denseRuns=0,splitRuns=0,knownLimits=0;',
        'int denseRuns=0,splitRuns=0,knownLimits=0;\nint r01Routes=0,residualRoutes=0,guardChecks=0;')
    s=once(s,'    auto p=TEST_NS::MakePlan(B,M,N,K,cores);','''#ifdef CHECK_R03
    bool useR01=bmms11::Eligible(B,M,N,K,cores);
    Mock::need(useR01||bmms11d::ResidualEligible(B,M,N,K,cores),"CPU fixture outside R03 dense domain");
    auto p=useR01?bmms11::MakePlan(B,M,N,K,cores):bmms11d::MakePlan(B,M,N,K,cores);
    if(useR01)++r01Routes;else ++residualRoutes;
#else
    auto p=TEST_NS::MakePlan(B,M,N,K,cores);
#endif''')
    s=once(s,'    Mock::Context ctx(2*p.blocks);Mock::Flags flags(p.blocks);',
        '''    Mock::Context ctx(2*p.blocks);Mock::Flags flags(p.blocks);
    RingAudit::State ringAudit(ring.data(),p.blocks,ring.size()/(2*p.blocks));RingAudit::active=&ringAudit;''')
    needle='''                Mock::logical=w-2*p.blocks;TEST_PRODUCER<T,TA,TB>op;
                op.Init(reinterpret_cast<GM_ADDR>(a.data()),reinterpret_cast<GM_ADDR>(b.data()),
                        reinterpret_cast<GM_ADDR>(ring.data()),p,&pipe);op.Process();'''
    replacement='''                Mock::logical=w-2*p.blocks;
                auto runProducer=[&](auto& op){op.Init(reinterpret_cast<GM_ADDR>(a.data()),reinterpret_cast<GM_ADDR>(b.data()),
                        reinterpret_cast<GM_ADDR>(ring.data()),p,&pipe);op.Process();};
#ifdef CHECK_R03
                if(useR01){bmms11::ReuseProducer<T,TA,TB> op;runProducer(op);}
                else{bmms11d::StagedProducer<T,TA,TB> op;runProducer(op);}
#else
                TEST_PRODUCER<T,TA,TB> op;runProducer(op);
#endif'''
    s=once(s,needle,replacement)
    needle='''                TEST_CONSUMER op;
                op.Init(reinterpret_cast<GM_ADDR>(ring.data()),reinterpret_cast<GM_ADDR>(part.data()),
                        reinterpret_cast<GM_ADDR>(y.data()),p,&pipe);op.Process();'''
    s=once(s,needle,'''                auto runConsumer=[&](auto& op){op.Init(reinterpret_cast<GM_ADDR>(ring.data()),reinterpret_cast<GM_ADDR>(part.data()),
                        reinterpret_cast<GM_ADDR>(y.data()),p,&pipe);op.Process();};
#ifdef CHECK_R03
                if(useR01){bmms11::RowMaxConsumer op;runConsumer(op);}
                else{bmms83::SmallKConsumer op;runConsumer(op);}
#else
                TEST_CONSUMER op;runConsumer(op);
#endif''')
    s=once(s,'        flags.drained();','''        flags.drained();ringAudit.drained();RingAudit::active=nullptr;
        RingAudit::lastReady=ringAudit.readyCount;RingAudit::lastFree=ringAudit.freeCount;
        RingAudit::lastReads=ringAudit.readElements;RingAudit::lastWrites=ringAudit.writeElements;''')
    s=once(s,'int main(){try{','''void guards(){
    for(int B:{0,1,3,64,65})for(int M:{1,16,80,128,144,8192,8193})for(int N:{1,16,128,256,272,8192})
    for(int K:{32,128,256,264,288,8192})for(int cores:{0,1,2,20,64,65}){
        bool common=B>=1&&B<=64&&cores>=1&&cores<=64&&M>=16&&M<=8192&&N>=16&&N<=8192&&
            M%16==0&&N%16==0&&K>=256&&K<=8192&&K%32==0&&int64_t(B)*M*K<=(1LL<<26)&&int64_t(B)*N*K<=(1LL<<26);
        bool r=bmms11::Eligible(B,M,N,K,cores),r2=bmms11r2::Eligible(B,M,N,K,cores);
        bool d=bmms11d::ResidualEligible(B,M,N,K,cores);
        Mock::need(r==r2,"R02 routing changed");
        Mock::need(!(r&&d)&&d==(common&&!r),"R03 overlaps R01 or accepts unsupported domain");++guardChecks;
    }
}
int main(){try{
#ifdef NEGATIVE_CONTROL
    dense<half,false,false>(1,128,256,256,1,0,false);return 7;
#endif
    guards();''')
    # Both newly modified protocols receive the parent cases; add full ring reuse
    # across 3/4 macro tiles and tasks plus a residual underfilled-macro fixture.
    needle='    dense<half,false,false>(1,128,256,256,1,4,false);'
    extra='''    for(int rev=0;rev<2;++rev){
        for(auto v:std::vector<std::array<int,5>>{{1,128,768,256,1},{1,272,528,288,1},{3,80,144,320,2},{1,128,256,256,20}}){
            auto[B,M,N,K,c]=v;dense<half,true,false>(B,M,N,K,c,0,rev);dense<bfloat16_t,false,true>(B,M,N,K,c,1,rev);
        }
    }
'''
    s=once(s,needle,extra+needle)
    needle='<<",\\\"plan_checks\\\":"<<planChecks'
    s=once(s,needle,needle+'<<",\\\"guard_checks\\\":"<<guardChecks<<",\\\"r01_route_runs\\\":"<<r01Routes<<",\\\"residual_route_runs\\\":"<<residualRoutes')
    needle='<<",\\\"publishes\\\":"<<Traffic::publishes.load()'
    s=once(s,needle,needle+'<<",\\\"ready_packets\\\":"<<RingAudit::lastReady<<",\\\"free_signals\\\":"<<RingAudit::lastFree<<",\\\"c_read_elements\\\":"<<RingAudit::lastReads')
    return s

def main():
    prepare();source=harness();(BUILD/'source_checks.cpp').write_text(source,encoding='utf-8',newline='\n')
    compiler=shutil.which(os.environ.get('CXX','g++'))
    if not compiler:raise RuntimeError('g++ required')
    configs={'R01':['-DTEST_NS=bmms11','-DTEST_PRODUCER=bmms11::ReuseProducer','-DTEST_CONSUMER=bmms11::RowMaxConsumer'],
        'R02':['-DTEST_NS=bmms11r2','-DTEST_PRODUCER=bmms11r2::ReuseProducer','-DTEST_CONSUMER=bmms11r2::RowMaxConsumer'],
        'R03':['-DCHECK_R03=1','-DTEST_NS=bmms11','-DTEST_PRODUCER=bmms11::ReuseProducer','-DTEST_CONSUMER=bmms11::RowMaxConsumer']}
    base=[compiler,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-pthread','-DCHECK_R01=1']
    runs={}
    for v,defs in configs.items():
        exe=BUILD/(v+('.exe' if os.name=='nt' else ''))
        call(base+defs+['source_checks.cpp','-o',str(exe)],v+'_compile')
        runs[v]=json.loads(call([str(exe)],v+'_run').stdout)
        (HERE/(v+'_CPU_RESULT.json')).write_text(json.dumps(runs[v],indent=2)+'\n',encoding='utf-8',newline='\n')
        print(v+': '+json.dumps({k:x for k,x in runs[v].items() if k!='output_bits'}),flush=True)
    assert runs['R01']['output_bits']==runs['R02']['output_bits']==runs['R03']['output_bits']
    for v in runs:
        assert runs[v]['strict_misses']==runs[v]['combined_misses']==0 and runs[v]['known_precision_limitations']==3
    a,b=runs['R01']['traffic_fixture'],runs['R02']['traffic_fixture']
    for k in a:
        if k not in ['ready_packets','free_signals']:assert a[k]==b[k],k
    assert (a['ready_packets'],b['ready_packets'])==(4,1) and (a['free_signals'],b['free_signals'])==(8,2)
    assert runs['R03']['r01_route_runs']>0 and runs['R03']['residual_route_runs']>0
    good=(BUILD/'ring_extracted.hpp').read_text(encoding='utf-8')
    broken=once(good,'if(mo+mr==ar&&no+nr==br)','if(mo==0&&no==0)')
    (BUILD/'ring_extracted.hpp').write_text(broken,encoding='utf-8',newline='\n')
    exe=BUILD/('negative'+('.exe' if os.name=='nt' else ''))
    try:
        call(base+configs['R02']+['-DNEGATIVE_CONTROL=1','source_checks.cpp','-o',str(exe)],'negative_compile')
        failure=call([str(exe)],'negative_run',expect_failure=True)
    finally:(BUILD/'ring_extracted.hpp').write_text(good,encoding='utf-8',newline='\n')
    result={'scope':'real source CPU layout/event/ownership model; not hardware simulation','cann_compiled_locally':False,'npu_tested_locally':False,
        'all_outputs_compared_bitwise':True,'known_numerical_limitations_remain':True,
        'fixture':{'B':1,'M':128,'N':256,'K':256,'cores':1},
        'negative_control':{'early_free_rejected':True,'exit_code':failure.returncode,'stderr':failure.stderr.strip()},
        'runs':{k:{kk:vv for kk,vv in v.items() if kk!='output_bits'} for k,v in runs.items()},
        'sources':{p.name:sha(p) for p in OUT.glob('*.asc')},
        'artifacts':{p.relative_to(ROOT).as_posix():sha(p) for p in [HERE/'build.py',Path(__file__),HERE/'ring_audit.hpp',
            HERE/'macro_ring_fragment.asc',HERE/'residual_dense_fragment.asc',ROOT/'V11_impl/run_checks.py',
            ROOT/'V11_impl/checks_tail.cpp',ROOT/'V11_impl/reuse_fragment.asc',ROOT/'V9_impl/dense_fragment.asc',
            ROOT/'V9_impl/source_checks.cpp',ROOT/'V9_impl/prepare_cpu.py',ROOT/'V9_impl/cube_model.hpp',ROOT/'next_stage/cpu_shim.hpp']}}
    for p in [HERE/'CHECKS.json',OUT/'CPU_CHECKS.json']:
        p.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('Three variants match; macro READY 4->1; premature FREE rejected.',flush=True)

if __name__=='__main__':main()

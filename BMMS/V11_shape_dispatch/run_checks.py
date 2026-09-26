"""Execute extracted R22 production kernels and compare with frozen R14.

The CPU model validates addresses, layouts, credits, capacities and results.
It does not emulate CANN compilation or hardware timing.
"""
from pathlib import Path
import importlib.util,json,shutil,subprocess,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;BUILD=HERE/'cpu_build'
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m
build=load('shape_builder',HERE/'build.py')
native=load('native_source_checks',ROOT/'V11_native_specialize/run_checks.py')
native.BUILD=BUILD;native.previous.BUILD=BUILD;native.previous.flex.BUILD=BUILD
native.previous.flex.redirect(native.previous.flex.prior)
once=build.once

def call(argv,stem,failure=None):
    r=subprocess.run(argv,cwd=BUILD,capture_output=True,text=True,timeout=600)
    build.write(BUILD/(stem+'.stdout.txt'),r.stdout);build.write(BUILD/(stem+'.stderr.txt'),r.stderr)
    if failure:assert r.returncode and failure in r.stderr,(stem,r.returncode,r.stderr[-3000:])
    elif r.returncode:raise RuntimeError(f'{stem}: {r.returncode}: {r.stderr[-3500:]}')
    return r

def prepare():
    native.prepare('R14')
    fragment=(HERE/'shape_fragment.asc').read_text(encoding='utf-8')
    assert fragment in (build.OUT/(build.NAME+'.asc')).read_text(encoding='utf-8')
    extract=native.previous.flex.prior.prior.prior.prior.parent.previous.parent.extract
    build.write(BUILD/'shape_extracted.hpp',extract(fragment,'// BMMS22_CPU_EXTRACT_END'))

def production_dispatch(producer):
    result=''
    for i,(enum,tag) in enumerate([('ShortN','sn'),('ShortM','sm'),('Dense','dn')]):
        tm,tn,am,bn,ks=build.CONFIGS[tag]
        result+=f'                {"if" if i==0 else "else if"}(useShape&&sel.strategy==bmms22::Strategy::{enum}){{\n'
        if producer:
            for j,k in enumerate(ks):
                result+=f'                    {"if" if j==0 else "else if"}(K=={k}){{bmms22::Producer<T,TA,TB,{k},{tm},{tn},{am},{bn}> op;runProducer(op);}}\n'
        else:result+=f'                    bmms22::Consumer<{tm},{tn},{am},{bn}> op;runConsumer(op);\n'
        result+='                }'
    return result+'else '

def harness(version):
    s=f'#define SHAPE_VARIANT {int(version=="R22")}\n#define BMMS22_CPU_TEST 1\n'+native.previous.flex.harness('R14')
    s=once(s,'#include "residual_extracted.hpp"','#include "residual_extracted.hpp"\n#include "dispatch_extracted.hpp"\n#include "shape_extracted.hpp"')
    s=once(s,'double maxError=0;','''int shapeRuns[4]={},nativeWorkChecks=0;
std::map<std::string,std::string> shapeFixtures;
std::string metrics();
double maxError=0;''')
    s=once(s,'    bool useSmall=bmms83::NativeEligible(M,N,K)&&!bmms71::UseResident(M,N,K);',
        '''    auto family=bmms8::Classify(B,M,N,K,TA,TB);
    bool useSmall=bmms83::NativeEligible(M,N,K)&&family!=bmms8::Family::Tiny&&family!=bmms8::Family::Resident;
    auto sel=bmms22::Select(B,M,N,K,std::is_same_v<T,half>?1:2,TA,TB,cores);
    bool useShape=SHAPE_VARIANT&&useSmall&&sel.strategy!=bmms22::Strategy::R14;''')
    s=once(s,'    if(useMacro)++macroRoutes;',
        '    if(useShape)p=sel.plan;\n    if(useSmall)++shapeRuns[useShape?int(sel.strategy):0];\n    if(useMacro)++macroRoutes;')
    s=once(s,'    OpStats::reset();','''    OpStats::reset();Traffic::reset();NativeTraffic::reset();
    TrafficAB::begin(reinterpret_cast<uintptr_t>(a.data()),a.size()*sizeof(T),reinterpret_cast<uintptr_t>(b.data()),b.size()*sizeof(T));''')
    s=once(s,'const auto ringBytes=useMacro?', 'const auto ringBytes=useShape?bmms22::RingBytes(sel):useMacro?')
    s=once(s,'    Mock::need(lastRingPerGroup==((useMacro||useSmall)?262144:65536),"wrong ring size for selected branch");',
        '''    const int tm=useShape?(sel.strategy==bmms22::Strategy::ShortM?32:sel.strategy==bmms22::Strategy::Dense?128:64):64;
    const int tn=useShape?(sel.strategy==bmms22::Strategy::ShortN?32:sel.strategy==bmms22::Strategy::ShortM?256:128):128;
    const int am=useShape&&sel.strategy==bmms22::Strategy::ShortM?32:256;
    Mock::need(lastRingPerGroup==(useSmall?uint64_t(8)*tm*tn*4:useMacro?262144:65536),"wrong ring size for selected branch");''')
    s=once(s,'                if(useMacro){bmms11r2::ReuseProducer',production_dispatch(True)+'if(useMacro){bmms11r2::ReuseProducer')
    s=once(s,'                if(useMacro){bmms11r2::RowMaxConsumer',production_dispatch(False)+'if(useMacro){bmms11r2::RowMaxConsumer')
    s=once(s,'        if(pattern>=4){','''        if(useSmall){
            int stages=0;
            for(int ms=0;ms<p.pM;++ms){int tiles=(ms+1)*p.mTiles/p.pM-ms*p.mTiles/p.pM;stages+=(tiles+am/tm-1)/(am/tm);}
            const uint64_t a0=uint64_t(B)*M*K*p.nTiles*sizeof(T),b0=uint64_t(B)*N*K*p.mTiles*sizeof(T);
            Mock::need(NativeTraffic::a0Bytes==a0&&NativeTraffic::b0Bytes==b0,"shape L0 byte oracle mismatch");
            Mock::need(Traffic::l0Bytes==a0+b0,"shape L0 total mismatch");
            Mock::need(Traffic::mmads==uint64_t(B)*p.mTiles*p.nTiles&&Traffic::publishes==Traffic::mmads,"shape tile count mismatch");
            Mock::need(Traffic::cWriteBytes==uint64_t(B)*M*N*4&&RingAudit::lastReads==uint64_t(B)*M*N,"shape C coverage mismatch");
            Mock::need(TrafficAB::aBytes==uint64_t(B)*M*K*p.pN*sizeof(T),"shape A GM traffic mismatch");
            Mock::need(TrafficAB::bBytes==uint64_t(B)*N*K*stages*sizeof(T),"shape B GM traffic mismatch");
            ++nativeWorkChecks;
            if(B==1&&cores==1&&!TA&&!TB&&std::is_same_v<T,half>&&pattern==0&&
               ((M==256&&N==16&&K==128)||(M==32&&N==512&&K==64)||(M==256&&N==512&&K==64))){
                std::string k="M"+std::to_string(M)+"_N"+std::to_string(N)+"_K"+std::to_string(K),v=metrics();
                if(shapeFixtures.count(k))Mock::need(shapeFixtures[k]==v,"shape logical-work repeat mismatch");shapeFixtures[k]=v;
            }
        }
        if(pattern>=4){''')
    s=once(s,'<<",\\\"manual_v_mte2\\\":"<<OpStats::manualVToMte2.load()<<"}";',
        '<<",\\\"manual_v_mte2\\\":"<<OpStats::manualVToMte2.load()<<",\\\"a0_bytes\\\":"<<NativeTraffic::a0Bytes.load()<<",\\\"b0_bytes\\\":"<<NativeTraffic::b0Bytes.load()<<"}";')
    s=once(s,'int main(){try{','''int main(){try{
#ifdef NEGATIVE_SHAPE_STRIDE
    dense<half,false,false>(1,80,16,128,1,0,false);
    if(strictMisses)throw std::runtime_error("narrow stride corrupts output");return 7;
#endif
#ifdef NEGATIVE_SHAPE_FOLD
    dense<half,false,false>(1,32,512,64,1,0,false);
    if(strictMisses)throw std::runtime_error("wide fold corrupts output");return 7;
#endif
''')
    s=once(s,'    std::ostringstream fixtures;', (HERE/'shape_cases.cpp.in').read_text(encoding='utf-8')+'\n    std::ostringstream fixtures;')
    s=once(s,'    std::cout<<std::setprecision(12)','''    std::ostringstream shapeDetails;bool firstShape=true;
    for(auto&[k,v]:shapeFixtures){if(!firstShape)shapeDetails<<",";firstShape=false;shapeDetails<<"\\\""<<k<<"\\\":"<<v;}
    std::cout<<std::setprecision(12)''')
    s=once(s,'<<",\\\"max_abs\\\":"<<maxError',
        '<<",\\\"native_work_checks\\\":"<<nativeWorkChecks<<",\\\"shape_route_runs\\\":["<<shapeRuns[0]<<","<<shapeRuns[1]<<","<<shapeRuns[2]<<","<<shapeRuns[3]<<"],\\\"shape_fixtures\\\":{"<<shapeDetails.str()<<"}"<<",\\\"max_abs\\\":"<<maxError')
    return s

def main():
    build.verify();BUILD.mkdir(exist_ok=True);compiler=shutil.which('g++');assert compiler
    args=[compiler,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-pthread','-DCHECK_R01=1','-DCHECK_R04=1','source_checks.cpp']
    runs={};old=json.loads((ROOT/'V11_flexible_grid/R14_CPU_RESULT.json').read_text(encoding='utf-8'))
    for version in ['R14','R22']:
        prepare();source=harness(version);build.write(BUILD/'source_checks.cpp',source);exe=BUILD/(version+'.exe')
        stamp={'source':build.sha(build.BASE if version=='R14' else build.OUT/(build.NAME+'.asc')),
               'harness':build.hashlib.sha256(source.encode()).hexdigest(),'headers':{p.name:build.sha(p) for p in BUILD.glob('*.hpp')}}
        stamp_path=HERE/(version+'_INPUTS.json')
        if '--resume' in sys.argv and stamp_path.exists() and json.loads(stamp_path.read_text(encoding='utf-8'))==stamp:
            data=json.loads((HERE/(version+'_CPU_RESULT.json')).read_text(encoding='utf-8'))
        else:
            call(args+['-o',str(exe)],version+'_compile');data=json.loads(call([str(exe)],version+'_run').stdout)
        build.write(stamp_path,json.dumps(stamp,indent=2)+'\n')
        assert data['strict_misses']==data['combined_misses']==0 and data['known_precision_limitations']==3
        for key,bits in old['output_bits'].items():assert data['output_bits'][key]==bits,(version,key)
        runs[version]=data;build.write(HERE/(version+'_CPU_RESULT.json'),json.dumps(data,indent=2)+'\n')
        print(version+': '+json.dumps({k:v for k,v in data.items() if k not in ['output_bits','reduction_checks','fixtures','shape_fixtures']}),flush=True)
    assert runs['R14']['output_bits']==runs['R22']['output_bits']
    assert all(x>0 for x in runs['R22']['shape_route_runs'])
    for key in ['M32_N512_K64','M256_N512_K64']:
        a,b=[runs[v]['shape_fixtures'][key] for v in ['R14','R22']]
        assert a['mmads']==2*b['mmads'] and a['fixpipes']==2*b['fixpipes']
        assert a['c_write_bytes']==b['c_write_bytes']
    a,b=[runs[v]['shape_fixtures']['M256_N16_K128'] for v in ['R14','R22']]
    assert b['duplicate_elements']<a['duplicate_elements'] and a['mmads']==b['mmads']
    negatives={}
    for name,old_text,new_text,define,error in [
        ('NARROW_STRIDE','vr,1,1,TN/8,AscendC::ReduceOrder','vr,1,1,16,AscendC::ReduceOrder','NEGATIVE_SHAPE_STRIDE','bounds'),
        ('WIDE_FOLD','if constexpr(TN==256){','if constexpr(TN==0){','NEGATIVE_SHAPE_FOLD','wide fold corrupts output')]:
        prepare();build.write(BUILD/'source_checks.cpp',harness('R22'));p=BUILD/'shape_extracted.hpp';good=p.read_text(encoding='utf-8')
        build.write(p,once(good,old_text,new_text));exe=BUILD/(name+'.exe')
        try:
            call(args+['-D'+define+'=1','-o',str(exe)],name+'_compile');run=call([str(exe)],name+'_run',failure=error)
        finally:build.write(p,good)
        negatives[name]={'rejected':True,'exit_code':run.returncode,'stderr':run.stderr.strip()};print(name+': rejected',flush=True)
    artifacts=dict(json.loads((ROOT/'V11_native_specialize/CHECKS.json').read_text(encoding='utf-8'))['artifacts'])
    for rel,digest in artifacts.items():assert build.sha(ROOT/rel)==digest
    for p in [HERE/'build.py',Path(__file__),HERE/'shape_cases.cpp.in',HERE/'host_plan.asc',HERE/'shape_fragment.asc',ROOT/'V11_native_specialize/run_checks.py']:
        artifacts[p.relative_to(ROOT).as_posix()]=build.sha(p)
    report={'scope':'extracted production source on CPU models, not CANN/NPU validation','sources':{p.name:build.sha(p) for p in build.OUT.glob('*.asc')},
            'composition':build.verify(),'ordinary_outputs_equal_bitwise':True,'negative_controls':negatives,
            'runs':{v:{k:x for k,x in data.items() if k!='output_bits'} for v,data in runs.items()},
            'artifacts':artifacts,'cann_compiled_locally':False,'npu_tested_locally':False,'known_numerical_limitations_remain':True}
    for p in [HERE/'CHECKS.json',build.OUT/'CPU_CHECKS.json']:build.write(p,json.dumps(report,indent=2)+'\n')
    print('R22 source execution, comparisons and fault checks passed.',flush=True)
if __name__=='__main__':main()

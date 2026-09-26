"""Execute extracted production source; validate Native layouts, outputs and logical work."""
from pathlib import Path
import importlib.util, json, re, shutil, subprocess, sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;BUILD=HERE/'cpu_build'
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m
build=load('native_builder',HERE/'build.py')
previous=load('resident_source_checks',ROOT/'V11_a_resident/run_checks.py')
previous.BUILD=BUILD;previous.flex.BUILD=BUILD;previous.flex.redirect(previous.flex.prior)
once=build.once
def call(argv,stem,failure=None):
    r=subprocess.run(argv,cwd=BUILD,capture_output=True,text=True,timeout=600)
    build.write(BUILD/(stem+'.stdout.txt'),r.stdout);build.write(BUILD/(stem+'.stderr.txt'),r.stderr)
    if failure:assert r.returncode and failure in r.stderr,(stem,r.returncode,r.stderr[-3000:])
    elif r.returncode:raise RuntimeError(f'{stem}: {r.returncode}: {r.stderr[-3500:]}')
    return r

def prepare(version):
    previous.prepare('R14')
    source=(build.BASE if version=='R14' else build.OUT/(build.NAMES[version]+'.asc')).read_text(encoding='utf-8')
    original=build.BASE.read_text(encoding='utf-8')
    common=(BUILD/'common_extracted.hpp').read_text(encoding='utf-8')
    # This range includes the new producer/selector in R20, before the unchanged consumers.
    actual=build.producer(source)
    common=once(common,build.producer(original),actual)
    build.write(BUILD/'common_extracted.hpp',common)
    shim=(BUILD/'cpu_shim.hpp').read_text(encoding='utf-8')
    shim=once(shim,'struct Buffer {std::vector<uint8_t> bytes,init;',
        'struct Buffer {int arena=-1;std::vector<uint8_t> bytes,init;')
    shim=once(shim,'b.storage=std::make_shared<Mock::Buffer>(n);charge<P>(n);',
        'b.storage=std::make_shared<Mock::Buffer>(n);b.storage->arena=P==TPosition::A2?2:P==TPosition::B2?3:-1;charge<P>(n);')
    build.write(BUILD/'cpu_shim.hpp',shim)
    model=(BUILD/'cube_model.hpp').read_text(encoding='utf-8')
    model=once(model,'namespace Traffic {','''namespace NativeTraffic {
inline std::atomic<uint64_t> a0Bytes{0},b0Bytes{0},a0Calls{0},b0Calls{0};
inline void reset(){a0Bytes=0;b0Bytes=0;a0Calls=0;b0Calls=0;}
}
namespace Traffic {''')
    model=once(model,'    Traffic::l0Bytes+=','''    Mock::need(d.b->arena==2||d.b->arena==3,"unclassified L0 operand");
    if(d.b->arena==2){NativeTraffic::a0Bytes+=uint64_t(p.repeatTimes)*256*sizeof(T);++NativeTraffic::a0Calls;}
    else{NativeTraffic::b0Bytes+=uint64_t(p.repeatTimes)*256*sizeof(T);++NativeTraffic::b0Calls;}
    Traffic::l0Bytes+=''')
    build.write(BUILD/'cube_model.hpp',model)

def harness(version):
    s=f'#define NATIVE_VARIANT {0 if version=="R14" else version[1:]}\n'+previous.flex.harness('R14')
    s=once(s,'#include "residual_extracted.hpp"','#include "residual_extracted.hpp"\n#include "dispatch_extracted.hpp"')
    s=once(s,'double maxError=0;','''int nativeWorkChecks=0,wideRuns=0,reuseRuns=0;
std::map<std::string,std::string> nativeFixtures;
std::string metrics();
double maxError=0;''')
    s=once(s,'    bool useSmall=bmms83::NativeEligible(M,N,K)&&!bmms71::UseResident(M,N,K);',
        '''    auto family=bmms8::Classify(B,M,N,K,TA,TB);
    bool useSmall=bmms83::NativeEligible(M,N,K)&&family!=bmms8::Family::Resident&&family!=bmms8::Family::Tiny;''')
    s=once(s,'    OpStats::reset();','''    const bool reuse=useSmall&&NATIVE_VARIANT==21&&p.nTiles>=2*p.pN;
    const bool wide=useSmall&&NATIVE_VARIANT==20&&p.nTiles>=2*p.pN;
    if(reuse)++reuseRuns;if(wide)++wideRuns;
    OpStats::reset();Traffic::reset();NativeTraffic::reset();
    TrafficAB::begin(reinterpret_cast<uintptr_t>(a.data()),a.size()*sizeof(T),reinterpret_cast<uintptr_t>(b.data()),b.size()*sizeof(T));''')
    if version=='R20':
        start='''                else if(useSmall){
                    if(K==32){bmms83::SmallKProducer<T,TA,TB,32> op;runProducer(op);}
                    else if(K==64){bmms83::SmallKProducer<T,TA,TB,64> op;runProducer(op);}
                    else{bmms83::SmallKProducer<T,TA,TB,128> op;runProducer(op);}
                }'''
        body=start[start.index('                    if(K'):start.rindex('                }')]
        new='                else if(useSmall){\n                    if(bmms83::UseWideN(p)){\n'+body.replace('SmallKProducer','WideNProducer')+'                    }else{\n'+body+'                    }\n                }'
        s=once(s,start,new)
    s=once(s,'        if(pattern>=4){','''        if(useSmall){
            int emittedN=0;
            for(int ns=0;ns<p.pN;++ns){int nt=(ns+1)*p.nTiles/p.pN-ns*p.nTiles/p.pN;emittedN+=wide?(nt+1)/2:nt;}
            uint64_t expectedA0=uint64_t(B)*M*K*(reuse?p.pN:emittedN)*sizeof(T);
            uint64_t expectedB0=uint64_t(B)*N*K*p.mTiles*sizeof(T);
            Mock::need(NativeTraffic::a0Bytes==expectedA0&&NativeTraffic::b0Bytes==expectedB0,"Native L0 byte oracle mismatch");
            Mock::need(Traffic::l0Bytes==expectedA0+expectedB0,"Native L0 accounting mismatch");
            Mock::need(Traffic::mmads==uint64_t(B)*p.mTiles*emittedN,"Native MMAD count mismatch");
            Mock::need(Traffic::publishes==uint64_t(B)*p.mTiles*p.nTiles,"Native Fixpipe count changed");
            Mock::need(Traffic::cWriteBytes==uint64_t(B)*M*N*4&&RingAudit::lastReads==uint64_t(B)*M*N,"Native ring coverage changed");
            Mock::need(TrafficAB::aBytes==uint64_t(B)*M*K*p.pN*sizeof(T),"Native GM A traffic changed");
            Mock::need(TrafficAB::bBytes==uint64_t(B)*N*K*bmms83::MStageCount(p.mTiles,p.pM)*sizeof(T),"Native GM B traffic changed");
            ++nativeWorkChecks;
            if(B==1&&M==256&&(N==1024||(N==16&&K==128))&&cores==1&&!TA&&!TB&&pattern==0){
                std::string k="K"+std::to_string(K)+"_N"+std::to_string(N),v=metrics();
                if(nativeFixtures.count(k))Mock::need(nativeFixtures[k]==v,"Native logical-work repeat mismatch");
                nativeFixtures[k]=v;
            }
        }
        if(pattern>=4){''')
    s=once(s,'<<",\\\"manual_v_mte2\\\":"<<OpStats::manualVToMte2.load()<<"}";',
        '<<",\\\"manual_v_mte2\\\":"<<OpStats::manualVToMte2.load()<<",\\\"a0_bytes\\\":"<<NativeTraffic::a0Bytes.load()<<",\\\"b0_bytes\\\":"<<NativeTraffic::b0Bytes.load()<<",\\\"a0_calls\\\":"<<NativeTraffic::a0Calls.load()<<",\\\"b0_calls\\\":"<<NativeTraffic::b0Calls.load()<<"}";')
    s=once(s,'int main(){try{','''int main(){try{
#ifdef NEGATIVE_NATIVE_FIX
    dense<half,false,false>(1,144,656,128,1,0,false);
    if(strictMisses)throw std::runtime_error("wide N source stride corrupts output");return 7;
#endif
#ifdef NEGATIVE_NATIVE_A0
    dense<half,true,false>(1,272,656,128,1,0,false);
    if(strictMisses)throw std::runtime_error("resident A0 address corrupts output");return 7;
#endif
''')
    s=once(s,'    std::ostringstream fixtures;', (HERE/'native_cases.cpp.in').read_text(encoding='utf-8')+'\n    std::ostringstream fixtures;')
    s=once(s,'    std::cout<<std::setprecision(12)','''    std::ostringstream nativeDetails;bool firstNative=true;
    for(auto&[k,v]:nativeFixtures){if(!firstNative)nativeDetails<<",";firstNative=false;nativeDetails<<"\\\""<<k<<"\\\":"<<v;}
    std::cout<<std::setprecision(12)''')
    s=once(s,'<<",\\\"max_abs\\\":"<<maxError',
        '<<",\\\"native_work_checks\\\":"<<nativeWorkChecks<<",\\\"wide_route_runs\\\":"<<wideRuns<<",\\\"reuse_route_runs\\\":"<<reuseRuns<<",\\\"native_fixtures\\\":{"<<nativeDetails.str()<<"}"<<",\\\"max_abs\\\":"<<maxError')
    return s

def main():
    build.verify();BUILD.mkdir(exist_ok=True);compiler=shutil.which('g++');assert compiler
    args=[compiler,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-pthread','-DCHECK_R01=1','-DCHECK_R04=1','source_checks.cpp']
    runs={};old=json.loads((ROOT/'V11_flexible_grid/R14_CPU_RESULT.json').read_text(encoding='utf-8'))
    for version in ['R14','R20','R21']:
        prepare(version);source=harness(version);build.write(BUILD/'source_checks.cpp',source);exe=BUILD/(version+'.exe')
        stamp={'production_sha256':build.sha(build.BASE if version=='R14' else build.OUT/(build.NAMES[version]+'.asc')),
               'harness_sha256':build.hashlib.sha256(source.encode()).hexdigest(),
               'headers':{p.name:build.sha(p) for p in BUILD.glob('*.hpp')}}
        stamp_path=HERE/(version+'_INPUTS.json')
        if '--resume' in sys.argv and stamp_path.exists() and json.loads(stamp_path.read_text(encoding='utf-8'))==stamp:
            data=json.loads((HERE/(version+'_CPU_RESULT.json')).read_text(encoding='utf-8'))
        else:
            call(args+['-o',str(exe)],version+'_compile');data=json.loads(call([str(exe)],version+'_run').stdout)
        build.write(stamp_path,json.dumps(stamp,indent=2)+'\n')
        assert data['strict_misses']==data['combined_misses']==0 and data['known_precision_limitations']==3
        for key,bits in old['output_bits'].items():assert data['output_bits'][key]==bits,(version,key)
        runs[version]=data;build.write(HERE/(version+'_CPU_RESULT.json'),json.dumps(data,indent=2)+'\n')
        print(version+': '+json.dumps({k:v for k,v in data.items() if k not in ['output_bits','reduction_checks','fixtures','native_fixtures']}),flush=True)
    assert runs['R14']['output_bits']==runs['R20']['output_bits']==runs['R21']['output_bits']
    assert runs['R20']['wide_route_runs']>0 and runs['R21']['reuse_route_runs']>0
    for k in ['K32_N1024','K64_N1024','K128_N1024']:
        a,b,c=[runs[v]['native_fixtures'][k] for v in ['R14','R20','R21']]
        assert a['mmads']==2*b['mmads']==c['mmads'] and a['a0_bytes']==2*b['a0_bytes']==8*c['a0_bytes']
        for key in ['b0_bytes','gm_bytes','fixpipes','c_write_bytes','ready','free','duplicate_elements','reduce_calls','reduce_rows','manual_v_mte2']:
            assert a[key]==b[key]==c[key],(k,key)
    narrow=[runs[v]['native_fixtures']['K128_N16'] for v in ['R14','R20','R21']]
    assert narrow[0]==narrow[1] and narrow[0]['b0_calls']==8*narrow[2]['b0_calls']
    negatives={}
    for version,name,old_text,new_text,define,error in [
        ('R20','WIDE_N_FIX_OFFSET','cc[(ni/16)*mr*16]','cc[0]','NEGATIVE_NATIVE_FIX','wide N source stride corrupts output'),
        ('R21','RESIDENT_A0_ADDRESS','reuseA?mo*TK:slot*TM*TK','reuseA?0:slot*TM*TK','NEGATIVE_NATIVE_A0','resident A0 address corrupts output')]:
        prepare(version);build.write(BUILD/'source_checks.cpp',harness(version));p=BUILD/'common_extracted.hpp';good=p.read_text(encoding='utf-8')
        build.write(p,once(good,old_text,new_text));exe=BUILD/(name+'.exe')
        try:
            call(args+['-D'+define+'=1','-o',str(exe)],name+'_compile');run=call([str(exe)],name+'_run',failure=error)
        finally:build.write(p,good)
        negatives[name]={'rejected':True,'exit_code':run.returncode,'stderr':run.stderr.strip()}
        print(name+': rejected as expected',flush=True)
    previous_checks=json.loads((ROOT/'V11_flexible_grid/CHECKS.json').read_text(encoding='utf-8'))
    artifacts=dict(previous_checks['artifacts'])
    for rel,digest in artifacts.items():assert build.sha(ROOT/rel)==digest,rel
    for p in [HERE/'build.py',Path(__file__),HERE/'native_cases.cpp.in',HERE/'R20_producer.asc',HERE/'R21_producer.asc',
              ROOT/'V11_a_resident/run_checks.py',ROOT/'V11_a_resident/traffic_audit.hpp',ROOT/'V11_flexible_grid/run_checks.py',ROOT/'V11_flexible_grid/R14_CPU_RESULT.json']:
        artifacts[p.relative_to(ROOT).as_posix()]=build.sha(p)
    report={'scope':'actual-source CPU layouts, memory, events and logical work; not CANN or hardware timing',
        'sources':{p.name:build.sha(p) for p in build.OUT.glob('*.asc')},'composition':build.verify(),
        'ordinary_outputs_equal_bitwise':True,'known_numerical_limitations_remain':True,'negative_controls':negatives,
        'runs':{v:{k:x for k,x in data.items() if k!='output_bits'} for v,data in runs.items()},
        'artifacts':artifacts,'cann_compiled_locally':False,'npu_tested_locally':False}
    for p in [HERE/'CHECKS.json',build.OUT/'CPU_CHECKS.json']:build.write(p,json.dumps(report,indent=2)+'\n')
    print('Native source checks and negative controls passed.',flush=True)

if __name__=='__main__':main()

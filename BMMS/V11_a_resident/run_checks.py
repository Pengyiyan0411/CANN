"""R14-based source checks, resident-A address/traffic audits and controlled faults."""
from pathlib import Path
import importlib.util,json,os,re,shutil,subprocess,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;BUILD=HERE/'cpu_build'
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m
build=load('resident_builder',HERE/'build.py');flex=load('flex_checks',ROOT/'V11_flexible_grid/run_checks.py')
flex.BUILD=BUILD;flex.redirect(flex.prior)
once=build.once
def call(argv,stem,failure=None):
    run=subprocess.run(argv,cwd=BUILD,capture_output=True,text=True,timeout=600)
    build.write(BUILD/(stem+'.stdout.txt'),run.stdout);build.write(BUILD/(stem+'.stderr.txt'),run.stderr)
    if failure:assert run.returncode!=0 and failure in run.stderr,(stem,run.returncode,run.stderr[-2500:])
    elif run.returncode:raise RuntimeError(f'{stem}: {run.returncode}: {run.stderr[-3000:]}')
    return run
def prepare(version):
    flex.prepare('R14');macro,residual=build.fragments(version)
    source=(build.BASE if version=='R14' else build.OUT/(build.NAMES[version]+'.asc')).read_text(encoding='utf-8')
    assert macro in source and residual in source
    extract=flex.prior.prior.prior.prior.parent.previous.parent.extract
    s=extract(macro,'// BMMS11R2_CPU_EXTRACT_END');c=flex.prior.build.consumer(s)
    helper='    __aicore__ inline void FinishReduction(){\n        const int worker=AscendC::GetBlockIdx();\n'+flex.prior.build.old_finish(macro)+'    }\n'
    c=once(c,'    __aicore__ inline void Process(){',helper+'    __aicore__ inline void Process(){')
    build.write(BUILD/'ring_extracted.hpp',once(s,flex.prior.build.consumer(s),c))
    build.write(BUILD/'residual_extracted.hpp',extract(residual,'// BMMS9_CPU_EXTRACT_END'))
    family=build.between(source,'enum class Family : int32_t {\n    Dot=0,','static inline int32_t MinH(')
    dispatch='namespace bmmmaxsum_v43 {\n'+build.function(source,'static inline bool UseTiny(int32_t M, int32_t N, int32_t K)')+'\n}\n'
    dispatch+='namespace bmms8 {\n'+family+build.function(source,'static inline bool IsFixedSmallK(')+'\n'+build.function(source,'static inline Family Classify(')+'\n}\n'
    build.write(BUILD/'dispatch_extracted.hpp',dispatch)
    shim=(BUILD/'cpu_shim.hpp').read_text(encoding='utf-8')
    shim=once(shim,'namespace OpStats {',(HERE/'traffic_audit.hpp').read_text(encoding='utf-8')+'\nnamespace OpStats {')
    shim=once(shim,'used[arena]+=n;OpStats::charge(arena,used[arena]);',
        'used[arena]+=n;if constexpr(arena==1)TrafficAB::chargeL1(used[arena]);OpStats::charge(arena,used[arena]);')
    build.write(BUILD/'cpu_shim.hpp',shim)
    model=(BUILD/'cube_model.hpp').read_text(encoding='utf-8')
    model=once(model,'    Traffic::gmInputBytes+=',
        '    TrafficAB::copied(reinterpret_cast<uintptr_t>(s.p),uint64_t(p.nValue)*p.dValue*sizeof(T));\n    Traffic::gmInputBytes+=')
    build.write(BUILD/'cube_model.hpp',model)

def harness(version):
    mode=15 if version=='R17' else 16 if version=='R18' else 0
    s=f'#define K_VARIANT {mode}\n#define HAS_RESIDENT {int(version=="R19")}\n'+flex.harness('R14')
    s=once(s,'#include "residual_extracted.hpp"','#include "residual_extracted.hpp"\n#include "dispatch_extracted.hpp"')
    s=once(s,'double maxError=0;',
        'int residentRuns=0,flowChecks=0;\nstd::map<std::string,std::string> flowFixtures;\nstd::string metrics();\ndouble maxError=0;')
    s=once(s,'    bool useMacro=bmms11r2::Eligible(B,M,N,K,cores);','''    auto family=bmms8::Classify(B,M,N,K,TA,TB);
    bool protectedFamily=family==bmms8::Family::Resident||family==bmms8::Family::Tiny;
    bool useMacro=bmms11r2::Eligible(B,M,N,K,cores)&&!protectedFamily;''')
    s=once(s,'useSmall||bmms11d::ResidualEligible(B,M,N,K,cores)',
        'useSmall||(bmms11d::ResidualEligible(B,M,N,K,cores)&&!protectedFamily)')
    s=once(s,'    OpStats::reset();','''    bool resident=false;
#if HAS_RESIDENT
    resident=useMacro&&bmms11r2::UseResidentA(p);
#endif
    if(resident)++residentRuns;
    TrafficAB::begin(reinterpret_cast<uintptr_t>(a.data()),a.size()*sizeof(T),
                     reinterpret_cast<uintptr_t>(b.data()),b.size()*sizeof(T));
    Traffic::reset();
    OpStats::reset();''')
    s=once(s,'                if(useMacro){bmms11r2::ReuseProducer<T,TA,TB> op;runProducer(op);}',
        '''                if(useMacro){
#if HAS_RESIDENT
                    if(resident){
                        if(K==256){bmms11r2::ResidentAProducer<T,TA,TB,256> op;runProducer(op);}
                        else{bmms11r2::ResidentAProducer<T,TA,TB,512> op;runProducer(op);}
                    }else
#endif
                    {bmms11r2::ReuseProducer<T,TA,TB> op;runProducer(op);}
                }''')
    s=once(s,'        if(pattern>=4){','''        if(useMacro){
            uint64_t oldA=uint64_t(B)*M*K*p.nTiles*sizeof(T);
            uint64_t expectedA=uint64_t(B)*M*K*(resident?p.pN:p.nTiles)*sizeof(T);
            uint64_t expectedB=uint64_t(B)*N*K*p.mTiles*sizeof(T);
            uint64_t aCalls=uint64_t(B)*p.mTiles*(resident?p.pN:p.nTiles*((K+255)/256));
            Mock::need(TrafficAB::aBytes==expectedA&&TrafficAB::aCopies==aCalls,"macro A copy count/bytes");
            Mock::need(TrafficAB::bBytes==expectedB,"macro B traffic changed");
            Mock::need(Traffic::gmInputBytes==expectedA+expectedB,"unclassified GM input");
            Mock::need(Traffic::l0Bytes==oldA+expectedB,"L1 to L0 traffic changed");
            Mock::need(Traffic::cWriteBytes==uint64_t(B)*M*N*4&&RingAudit::lastReads==uint64_t(B)*M*N,"C traffic changed");
            Mock::need(Traffic::mmads==uint64_t(B)*((M+63)/64)*((N+127)/128)*((K+63)/64),"MMAD count changed");
            Mock::need(RingAudit::lastReady==uint64_t(B)*p.mTiles*p.nTiles&&RingAudit::lastFree==2*RingAudit::lastReady,"ring credit count changed");
            if(resident)Mock::need(expectedA<oldA,"resident path did not save A reads");
            ++flowChecks;
            if(B==1&&M==128&&N==1024&&cores==1&&(K==256||K==512)&&!TA&&!TB&&pattern==0){
                std::string k="K"+std::to_string(K);
                std::string v=metrics();
                if(flowFixtures.count(k))Mock::need(flowFixtures[k]==v,"logical traffic changed on repeat");
                flowFixtures[k]=v;
            }
        }
        if(pattern>=4){''')
    s=once(s,'<<",\\\"manual_v_mte2\\\":"<<OpStats::manualVToMte2.load()<<"}";',
        '<<",\\\"manual_v_mte2\\\":"<<OpStats::manualVToMte2.load()<<",\\\"a_gm_bytes\\\":"<<TrafficAB::aBytes.load()<<",\\\"b_gm_bytes\\\":"<<TrafficAB::bBytes.load()<<",\\\"a_copies\\\":"<<TrafficAB::aCopies.load()<<",\\\"b_copies\\\":"<<TrafficAB::bCopies.load()<<",\\\"l1_peak_bytes\\\":"<<TrafficAB::l1Peak.load()<<"}";')
    if mode:
        domains=(ROOT/'V11_k_coverage/domain_checks.cpp.in').read_text(encoding='utf-8')
        s=once(s,'int main(){try{',domains+'\nint main(){try{\n    domainChecksAll();')
        s=once(s,'    std::ostringstream fixtures;',(ROOT/'V11_k_coverage/new_domain_cases.cpp.in').read_text(encoding='utf-8')+'\n    std::ostringstream fixtures;')
    else:
        s=once(s,'int main(){try{','int main(){try{\n'+'''
#ifdef NEGATIVE_A_ADDRESS
    dense<half,true,false>(1,144,528,512,1,0,false);
    if(strictMisses)throw std::runtime_error("resident A address reference mismatch");return 7;
#endif
#ifdef NEGATIVE_A_REFRESH
    dense<half,false,false>(1,144,528,256,1,0,false);return 7;
#endif
''')
        s=once(s,'    std::ostringstream fixtures;',(HERE/'resident_cases.cpp.in').read_text(encoding='utf-8')+'\n    std::ostringstream fixtures;')
    s=once(s,'    std::cout<<std::setprecision(12)',
        '''    std::ostringstream flows;bool firstFlow=true;
    for(auto&[k,v]:flowFixtures){if(!firstFlow)flows<<",";firstFlow=false;flows<<"\\\""<<k<<"\\\":"<<v;}
    std::cout<<std::setprecision(12)''')
    s=once(s,'<<",\\\"max_abs\\\":"<<maxError',
        '<<",\\\"resident_route_runs\\\":"<<residentRuns<<",\\\"dataflow_checks\\\":"<<flowChecks<<",\\\"dataflow_fixtures\\\":{"<<flows.str()<<"}"'+
        ( '<<",\\\"domain_checks\\\":"<<domainChecks' if mode else '')+'<<",\\\"max_abs\\\":"<<maxError')
    return s

def host_check(compiler):
    macro=build.fragments('R19')[0]
    body=build.between(macro,'    if(UseResidentA(p)){','#undef BMMS11R2_LAUNCH')
    selector=build.function(macro,'static inline bool UseResidentA(')
    bindings=re.findall(r'^BMMS19_KERNEL\((\w+),(\w+),(true|false),(true|false),(256|512)\)$',macro,re.M)
    assert len(bindings)==16
    for name,t,ta,tb,k in bindings:
        assert name==f'bmms19_k{k}_{"f16" if t=="half" else "b16"}_{"t" if ta=="true" else "n"}{"t" if tb=="true" else "n"}'
    code='''#include <string>
#include <iostream>
#include <stdexcept>
struct Plan {int K,pN,nTiles;};
'''+selector+'''
std::string choose(Plan p,int dtype,bool ta,bool tb){int K=p.K;std::string selected;
#define BMMS11R2_LAUNCH(NAME) selected=#NAME
'''+body+'''
#undef BMMS11R2_LAUNCH
return selected;}
int main(){int checked=0,used=0;
for(int K:{32,128,256,288,512,544,8192})for(int nt=1;nt<=32;++nt)for(int pn=1;pn<=nt;++pn){
    Plan p{K,pn,nt};bool allMulti=true;
    for(int ns=0;ns<pn;++ns)allMulti&=((ns+1)*nt/pn-ns*nt/pn)>=2;
    bool expect=(K==256||K==512)&&allMulti;
    if(UseResidentA(p)!=expect)throw std::runtime_error("resident gate mismatch");
    for(int dtype:{1,2})for(bool ta:{false,true})for(bool tb:{false,true}){
        std::string prefix=expect?"bmms19_k"+std::to_string(K):"bmms11r2";
        std::string expected=prefix+(dtype==1?"_f16_":"_b16_")+(ta?"t":"n")+(tb?"t":"n");
        if(choose(p,dtype,ta,tb)!=expected)throw std::runtime_error("host kernel dispatch mismatch");
        ++checked;if(expect)++used;
    }
}
std::cout<<"{\\\"checked\\\":"<<checked<<",\\\"resident_dispatches\\\":"<<used<<",\\\"bindings\\\":16}\\n";}
'''
    build.write(BUILD/'host_checks.cpp',code);exe=BUILD/'host_checks.exe'
    call([compiler,'-std=c++20','-O2','host_checks.cpp','-o',str(exe)],'host_compile')
    report=json.loads(call([str(exe)],'host_run').stdout);build.write(HERE/'HOST_CHECKS.json',json.dumps(report,indent=2)+'\n');return report

def main():
    build.verify();BUILD.mkdir(exist_ok=True);compiler=shutil.which(os.environ.get('CXX','g++'));assert compiler
    host=host_check(compiler);print('Host: '+json.dumps(host),flush=True)
    args=[compiler,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-pthread','-DCHECK_R01=1','-DCHECK_R04=1','source_checks.cpp']
    old=json.loads((ROOT/'V11_flexible_grid/R14_CPU_RESULT.json').read_text(encoding='utf-8'));runs={}
    for version,count in [('R14',554),('R17',640),('R18',752),('R19',554)]:
        prepare(version);build.write(BUILD/'source_checks.cpp',harness(version));exe=BUILD/(version+'.exe')
        call(args+['-o',str(exe)],version+'_compile');data=json.loads(call([str(exe)],version+'_run').stdout);runs[version]=data
        assert data['source_runs']==count,(version,data['source_runs'])
        assert data['strict_misses']==data['combined_misses']==0 and data['known_precision_limitations']==3
        for key,bits in old['output_bits'].items():assert data['output_bits'][key]==bits,(version,key)
        assert data['peak_arena_bytes']==old['peak_arena_bytes']
        if version=='R19':assert data['resident_route_runs']>0
        else:assert data['resident_route_runs']==0
        build.write(HERE/(version+'_CPU_RESULT.json'),json.dumps(data,indent=2)+'\n')
        print(version+': '+json.dumps({k:v for k,v in data.items() if k not in ['output_bits','reduction_checks','fixtures']}),flush=True)
    assert runs['R14']['output_bits']==runs['R19']['output_bits']
    for v,previous in [('R17','R15'),('R18','R16')]:
        prev=json.loads((ROOT/f'V11_k_coverage/{previous}_CPU_RESULT.json').read_text(encoding='utf-8'))
        for key,bits in prev['output_bits'].items():assert runs[v]['output_bits'][key]==bits,(v,key)
    for k in ['K256','K512']:
        a=runs['R14']['dataflow_fixtures'][k];b=runs['R19']['dataflow_fixtures'][k]
        assert b['a_gm_bytes']*4==a['a_gm_bytes'] and b['gm_bytes']*4==a['gm_bytes']*3
        for key in ['b_gm_bytes','l0_bytes','l0_calls','mmads','fixpipes','c_write_bytes','ready','free','reduce_calls','reduce_rows']:
            assert a[key]==b[key],(k,key)
        assert b['l1_peak_bytes']==(320*1024 if k=='K256' else 384*1024)
    negatives={}
    for name,a,b,define,error in [
        ('A_TRANSPOSE_STRIDE','(mo/16+i)*RK*16+ak*16','(mo/16+i)*kr1*16+ak*16','NEGATIVE_A_ADDRESS','resident A address reference mismatch'),
        ('A_K_BASE','const int ak=kBase+kk;','const int ak=kk;','NEGATIVE_A_ADDRESS','resident A address reference mismatch'),
        ('A_REFRESH','                LoadResidentA(batch,m0,ar);','                if(m0==mBegin)LoadResidentA(batch,m0,ar);','NEGATIVE_A_REFRESH','macro A copy count/bytes')]:
        prepare('R19');build.write(BUILD/'source_checks.cpp',harness('R19'));path=BUILD/'ring_extracted.hpp';good=path.read_text(encoding='utf-8')
        build.write(path,once(good,a,b));exe=BUILD/(name+'.exe')
        try:
            call(args+['-D'+define+'=1','-o',str(exe)],name+'_compile')
            run=call([str(exe)],name+'_run',failure=error)
        finally:build.write(path,good)
        negatives[name]={'rejected':True,'exit_code':run.returncode,'stderr':run.stderr.strip()}
    artifacts={}
    for rel in ['V11_flexible_grid/CHECKS.json','V11_k_coverage/CHECKS.json']:
        check=json.loads((ROOT/rel).read_text(encoding='utf-8'));artifacts.update(check['artifacts']);artifacts[rel]=build.sha(ROOT/rel)
    for rel,digest in artifacts.items():assert build.sha(ROOT/rel)==digest,rel
    for path in [HERE/'build.py',Path(__file__),HERE/'traffic_audit.hpp',HERE/'resident_cases.cpp.in',HERE/'resident_producer.asc',
                 ROOT/'V11_flexible_grid/run_checks.py',ROOT/'V11_flexible_grid/R14_CPU_RESULT.json',
                 ROOT/'V11_k_coverage/R15_CPU_RESULT.json',ROOT/'V11_k_coverage/R16_CPU_RESULT.json',*HERE.glob('*_fragment.asc')]:
        artifacts[path.relative_to(ROOT).as_posix()]=build.sha(path)
    report={'scope':'actual-source CPU arithmetic/storage/event checks, logical copy traffic and translated host dispatch; no hardware timing',
        'sources':{p.name:build.sha(p) for p in build.OUT.glob('*.asc')},'composition':build.verify(),
        'old_464_ordinary_outputs_equal_archived_R14':True,'R14_R19_ordinary_outputs_equal_bitwise':True,
        'coverage_descendants_match_existing_coverage_outputs':True,'host_checks':host,'negative_controls':negatives,
        'runs':{k:{kk:vv for kk,vv in v.items() if kk!='output_bits'} for k,v in runs.items()},
        'known_numerical_limitations_remain':True,'cann_compiled_locally':False,'npu_tested_locally':False,'artifacts':artifacts}
    for p in [HERE/'CHECKS.json',build.OUT/'CPU_CHECKS.json']:build.write(p,json.dumps(report,indent=2)+'\n')
    print('Three independent R14 descendants, measured logical traffic and three resident-A fault checks passed.',flush=True)
if __name__=='__main__':main()

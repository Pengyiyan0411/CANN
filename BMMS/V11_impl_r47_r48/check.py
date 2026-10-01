"""Execute extracted real producer/consumer C++ in the inherited CPU model."""
from pathlib import Path
import shutil,subprocess,json,hashlib
import build as b
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;D=HERE/'cpu_build'
def replace_span(s,a,z,new):return s[:s.index(a)]+new+s[s.index(z,s.index(a)):]
def prepare():
    D.mkdir(exist_ok=True)
    for p in (ROOT/'V11_multiroute29_31/cpu_build').glob('*.hpp'):shutil.copyfile(p,D/p.name)
    for n in [47,48]:shutil.copyfile(HERE/f'r{n}_extracted.hpp',D/f'r{n}_extracted.hpp')
    # Extend, rather than disable, the previous half-row ownership audit.
    # R48's guard launches exactly one batch per group; owner is batch&1.
    p=D/'cpu_shim.hpp';s=p.read_text(encoding='utf-8')
    s=b.once(s,'int wholeTileElements=0;','int wholeTileElements=0;bool batchOwner=false;')
    s=b.once(s,'if(wholeTileElements){','if(batchOwner){Mock::need(Mock::subId==(Mock::pairId&1)&&s.reads[Mock::subId]<=s.writes,"wrong batch owner or duplicate read");}\n        else if(wholeTileElements){')
    s=b.once(s,'const uint64_t expected=wholeTileElements?','const uint64_t expected=batchOwner?(Mock::subId==(Mock::pairId&1)?s.writes:0):wholeTileElements?')
    b.write(p,s)
    s=(ROOT/'V11_multiroute29_31/source_checks.cpp.in').read_text(encoding='utf-8')
    s=s.replace('#include "r29_extracted.hpp"\n#include "r30_extracted.hpp"\n#include "r31_extracted.hpp"','#include "r47_extracted.hpp"\n#include "r48_extracted.hpp"')
    s=s.replace('routeRuns[3]','routeRuns[2]').replace('routeRuns[route-29]','routeRuns[route-47]')
    s=replace_span(s,'    if(route==29){','    std::vector<float>ws', '''    if(route==47){Mock::need(bmms47::Eligible(B,M,N,K,cores),"R47 fixture outside guard");
        p=CANDIDATE?bmms47::MakePlan(B,M,N,K,cores):bmms83::MakeNative(B,M,N,K,cores);
        rb=CANDIDATE?bmms47::RingBytes(p):bmms83::NativeRingBytes(p);pb=M*4;
        slotElements=CANDIDATE?64*64:4*64*128;}
    if(route==48){Mock::need(bmms48::Eligible(B,M,N,K,cores),"R48 fixture outside guard");
        p=CANDIDATE?bmms48::MakePlan(B,M,N,K,cores):bmms11d::MakePlan(B,M,N,K,cores);
        rb=bmms11d::RingBytes(p);pb=CANDIDATE?0:bmms11d::PartialBytes(p);slotElements=64*128;}
''')
    s=s.replace('RingAudit::active=&ring;','ring.batchOwner=CANDIDATE&&route==48;RingAudit::active=&ring;')
    s=replace_span(s,'            if(CANDIDATE){','        },reverse);', '''            if(CANDIDATE){
                if(route==47){bmms47::Entry<T,TA,TB>((GM_ADDR)a.data(),(GM_ADDR)b.data(),(GM_ADDR)y.data(),(GM_ADDR)ws.data(),(GM_ADDR)part,p);return;}
                if(route==48){bmms48::Entry<T,TA,TB>((GM_ADDR)a.data(),(GM_ADDR)b.data(),(GM_ADDR)y.data(),(GM_ADDR)ws.data(),(GM_ADDR)part,p);return;}
            }
            if(route==47){bmms25::Entry<T,TA,TB,false>((GM_ADDR)a.data(),(GM_ADDR)b.data(),(GM_ADDR)y.data(),(GM_ADDR)ws.data(),(GM_ADDR)part,p);return;}
            AscendC::TPipe pipe;
            if(Mock::cube){bmms11d::StagedProducer<T,TA,TB> op;op.Init((GM_ADDR)a.data(),(GM_ADDR)b.data(),(GM_ADDR)ws.data(),p,&pipe);op.Process();}
            else{bmms83::SmallKConsumer op;op.Init((GM_ADDR)ws.data(),(GM_ADDR)part,(GM_ADDR)y.data(),p,&pipe);op.Process();}
''')
    s=s.replace('ctx.barrier.generation==1,"unexpected barrier count"','ctx.barrier.generation==(CANDIDATE&&route==48?0:1),"unexpected barrier count"')
    s=replace_span(s,'        const uint64_t tiles=','        std::vector<uint32_t>bits;', '''        uint64_t tiles=uint64_t(B)*((M+63)/64)*((N+127)/128);
        if(CANDIDATE&&route==47){tiles=0;for(int g=0;g<p.blocks;++g){
            const int lo=g*p.mTiles/p.pM*16,hi=(g+1)*p.mTiles/p.pM*16;
            tiles+=(hi-lo+63)/64;}}
        Mock::need(Traffic::mmads==tiles*(route==48?(K+127)/128:1),"arithmetic tile count changed unexpectedly");
''')
    s=s.replace('<<",\\\"ready\\\":"<<ring.readyCount','<<",\\\"barriers\\\":"<<ctx.barrier.generation<<",\\\"partial_bytes\\\":"<<pb<<",\\\"ready\\\":"<<ring.readyCount')
    s=replace_span(s,'#ifdef NEGATIVE_29','    std::cout<<std::setprecision', '''#ifdef NEGATIVE_OWNER
    run<half,false,false>(48,2,80,144,288,4,1,false);Mock::need(misses==0,"invalid zero padding");return 7;
#endif
#ifdef NEGATIVE_PADDING
    run<half,false,false>(47,1,272,48,128,3,1,false);Mock::need(misses==0,"invalid padding consumed");return 7;
#endif
    for(int rev=0;rev<2;++rev){
        for(auto s:std::vector<std::array<int,3>>{{272,48,3},{528,64,8},{1056,48,20}}){
            layouts<half>(47,1,s[0],s[1],128,s[2],0,rev);layouts<bfloat16_t>(47,1,s[0],s[1],128,s[2],3,rev);}
        run<half,true,true>(47,1,8192,48,128,2,1,rev);
        run<bfloat16_t,false,true>(47,1,272,64,128,64,2,rev);
        for(auto s:std::vector<std::array<int,5>>{{2,16,16,256,3},{2,48,144,288,4},{3,80,48,384,4},{2,112,240,480,4}}){
            layouts<half>(48,s[0],s[1],s[2],s[3],s[4],0,rev);layouts<bfloat16_t>(48,s[0],s[1],s[2],s[3],s[4],3,rev);}
        for(int K:{320,352,416,448}){
            run<half,true,true>(48,2,32,128,K,4,1,rev);run<bfloat16_t,false,true>(48,2,64,64,K,3,2,rev);}
    }
''')
    s=s.replace('<<","<<routeRuns[2]','')
    b.write(D/'source_checks.cpp',s)
def call(args,stem):
    p=subprocess.run(args,cwd=D,capture_output=True,text=True,timeout=900)
    b.write(D/(stem+'.stdout.txt'),p.stdout);b.write(D/(stem+'.stderr.txt'),p.stderr)
    if p.returncode:raise RuntimeError(stem+': '+p.stderr[-3000:]+p.stdout[-500:])
    return p.stdout
def main():
    b.main();prepare();compiler=shutil.which('g++');assert compiler
    args=[compiler,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-pthread','-DCHECK_R01=1','source_checks.cpp']
    runs={}
    for name,mode in [('BASELINE',0),('CANDIDATES',1)]:
        exe=D/(name+'.exe');call(args+['-DCANDIDATE='+str(mode),'-o',str(exe)],name+'_compile')
        print(name+' compiled',flush=True)
        runs[name]=json.loads(call([str(exe)],name+'_run'));assert runs[name]['strict_misses']==0
        b.write(HERE/(name+'_CPU_RESULT.json'),json.dumps(runs[name],indent=2)+'\n')
        print(name+': '+json.dumps({k:v for k,v in runs[name].items() if k not in ['fixtures','output_bits']}),flush=True)
    assert runs['BASELINE']['output_bits']==runs['CANDIDATES']['output_bits']
    report={'scope':'actual C++ source replay in CPU storage/event/arithmetic model, not CANN compilation or NPU execution',
        'bitwise_equal_to_baseline_in_model':True,'CANN_compiled':False,'NPU_tested':False,
        'runs':{k:{a:v for a,v in r.items() if a!='output_bits'} for k,r in runs.items()},
        'model_headers':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in D.glob('*.hpp')}}
    b.write(b.OUT/'CPU_CHECKS.json',json.dumps(report,indent=2)+'\n')
    print('Baseline bitwise comparison passed.',flush=True)
if __name__=='__main__':main()

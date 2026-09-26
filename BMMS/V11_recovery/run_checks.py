"""Run actual R08/R09/R10 source models, exact one-wave costs and residual packet mutants."""
from pathlib import Path
import importlib.util
import json
import os
import shutil
import sys

HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;BUILD=HERE/'cpu_build'
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m
build=load('recovery_build',HERE/'build.py')
prior=load('packet_checks',ROOT/'V11_grid_packets/run_checks.py')
prior.BUILD=prior.prior.BUILD=prior.prior.parent.BUILD=prior.prior.parent.previous.BUILD=prior.prior.parent.previous.parent.BUILD=BUILD
once=build.once;call=prior.call

def prepare(version):
    prior.prepare('R08')
    if version=='R08':return
    source=(build.OUT/(build.NAMES[version]+'.asc')).read_text(encoding='utf-8')
    frag,target,marker=('residual_packet_fragment.asc','residual_extracted.hpp','// BMMS9_CPU_EXTRACT_END') if version=='R09' else (
        'one_wave_macro_fragment.asc','ring_extracted.hpp','// BMMS11R2_CPU_EXTRACT_END')
    text=(HERE/frag).read_text(encoding='utf-8');assert text in source
    build.write(BUILD/target,prior.prior.parent.previous.parent.extract(text,marker))

def harness(version):
    s=prior.harness('R08')
    if version=='R09':
        s=once(s,'Mock::need(lastRingPerGroup==((useMacro||useSmall)?262144:65536),"wrong ring size for selected branch");',
            'Mock::need(lastRingPerGroup==262144,"wrong ring size for selected branch");')
        s=once(s,'else{bmms83::SmallKConsumer op;runConsumer(op);}',
            'else{bmms83::SmallKPacketConsumer op;runConsumer(op);}')
    if version=='R10':
        s=once(s,'''        Mock::need(p.mTiles==r2.mTiles&&p.nTiles==r2.nTiles&&p.pM==r2.pM&&p.pN==r2.pN&&
            p.tasks==r2.tasks&&p.blocks==r2.blocks,"merged macro plan differs from R01");''',
            '''        Mock::need(p.mTiles==r2.mTiles&&p.nTiles==r2.nTiles&&p.tasks==r2.tasks&&p.blocks==r2.blocks,
            "single-wave plan altered launch/task count");
        if(p.pM!=r2.pM||p.pN!=r2.pN){
            Mock::need(p.tasks==p.blocks&&r2.tasks==r2.B*r2.pM*r2.pN,"changed multi-wave plan");
            auto a=bmms11r2::SingleWavePeak(p),b=bmms11r2::SingleWavePeak(r2);
            Mock::need(8*b.tiles<=7*a.tiles&&8*b.cells<=7*a.cells&&8*b.input<=7*a.input,"grid margin violated");
        }''')
    s=once(s,'    guards();', '''#ifdef NEGATIVE_RESIDUAL_FREE
    dense<half,false,false>(1,64,512,256,1,0,false);return 7;
#endif
#ifdef NEGATIVE_RESIDUAL_FLUSH
    dense<half,false,false>(1,16,384,352,1,0,false);return 7;
#endif
    guards();''')
    s=once(s,'    std::ostringstream fixtures;', '''    for(int rev=0;rev<2;++rev){
        for(auto d:std::vector<std::array<int,5>>{
            {1,16,128,256,1},{1,16,256,288,1},{1,16,384,352,1},
            {1,80,1040,288,2},{3,80,144,288,2}}){
            layouts<half>(d,0,rev);layouts<bfloat16_t>(d,0,rev);
        }
        dense<half,false,false>(1,64,640,4096,1,0,rev);
        dense<bfloat16_t,true,true>(1,8192,16,288,4,1,rev);
        // This shape actually changes R10 from 6x1 to 3x2 with exactly six tasks.
        dense<half,false,true>(1,1024,512,256,6,0,rev);
        dense<bfloat16_t,true,false>(1,1024,512,256,6,1,rev);
    }
    std::ostringstream fixtures;''')
    return s

def grid_check(compiler):
    template=(ROOT/'V11_grid_packets/grid_checks.cpp.in').read_text(encoding='utf-8')
    parts=[]
    for ns,path in [('baseline',ROOT/'V11_followup/macro_ring_fragment.asc'),('candidate',HERE/'one_wave_macro_fragment.asc')]:
        fragment=path.read_text(encoding='utf-8')
        body=build.between(fragment,'namespace bmms11r2 {','static inline uint64_t RingBytes(')
        parts.append(body.replace('namespace bmms11r2 {','namespace '+ns+' {',1)+'}\n')
    s=once(template,'// INSERT_PLANS','\n'.join(parts))
    s=once(s,'    int count=0,changed=0;', '''    int count=0,changed=0,extentChecks=0;
    for(int tile:{128,256})for(int x=16;x<=8192;x+=16){
        int tiles=(x+tile-1)/tile;
        for(int parts=1;parts<=std::min(64,tiles);++parts){
            int peak=0;
            for(int i=0;i<parts;++i){int lo=i*tiles/parts,hi=(i+1)*tiles/parts;
                peak=std::max(peak,std::min(x,hi*tile)-lo*tile);}
            need(candidate::PeakExtent(x,tile,parts)==peak,"wrong closed-form extent");++extentChecks;
        }
    }''')
    s=once(s,'for(int cores:{1,2,3,8,20,32,64})for(int tail:{0,16})',
        'for(int cores:{1,2,3,6,8,20,32,64})for(int tail:{0,16,48,112})')
    s=once(s,'int M=mt*128-(tail?112:0),N=nt*256-(tail?240:0);',
        'int M=mt*128-tail,N=nt*256-(tail==112?240:tail);')
    s=once(s,'''        auto a=walk(old),b=walk(p);auto pred=candidate::PeakForGrid(p);
        need(pred.tiles==b.tiles&&pred.cells==b.cells&&pred.input==b.input,"cost disagrees with device traversal");''',
        '''        auto a=walk(old),b=walk(p);
        need(p.tasks==old.tasks&&p.blocks==old.blocks,"changed launch/task count");
        if(p.tasks==p.blocks){auto pred=candidate::SingleWavePeak(p);
            need(pred.tiles==b.tiles&&pred.cells==b.cells&&pred.input==b.input,"cost disagrees with device traversal");}
        else need(old.pM==p.pM&&old.pN==p.pN,"changed multi-wave baseline");''')
    s=once(s,'            need(b.tiles*8<=a.tiles*7',
        '            need(p.tasks==p.blocks,"changed multi-wave plan");\n            need(b.tiles*8<=a.tiles*7')
    s=once(s,'<<count<<",\\\"changed\\\":"<<changed',
        '<<count<<",\\\"extent_checks\\\":"<<extentChecks<<",\\\"changed\\\":"<<changed')
    s=once(s,'{{1,384,768,256,5},{1,1024,1024,256,20},',
        '{{1,1024,512,256,6},{1,384,768,256,5},{1,1024,1024,256,20},')
    build.write(BUILD/'grid_checks.cpp',s)
    exe=BUILD/'grid_checks.exe';call([compiler,'-std=c++20','-O2','grid_checks.cpp','-o',str(exe)],'grid_compile')
    data=json.loads(call([str(exe)],'grid_run').stdout)
    assert data['checked']>6000 and data['changed']>0 and data['extent_checks']>20000
    build.write(HERE/'GRID_CHECKS.json',json.dumps(data,indent=2)+'\n')
    print('Grid: '+json.dumps(data),flush=True);return data

def main():
    build.verify();prepare('R08');compiler=shutil.which(os.environ.get('CXX','g++'));assert compiler
    grid=grid_check(compiler)
    args=[compiler,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-pthread',
          '-DCHECK_R01=1','-DCHECK_R04=1','source_checks.cpp']
    runs={}
    for version in ['R08','R09','R10']:
        prepare(version);build.write(BUILD/'source_checks.cpp',harness(version));exe=BUILD/(version+'.exe')
        call(args+['-o',str(exe)],version+'_compile')
        data=json.loads(call([str(exe)],version+'_run').stdout);runs[version]=data
        assert data['strict_misses']==data['combined_misses']==0 and data['known_precision_limitations']==3
        assert data['source_runs']==444 and data['repeat_pairs']==222,(version,data['source_runs'],data['repeat_pairs'])
        build.write(HERE/(version+'_CPU_RESULT.json'),json.dumps(data,indent=2)+'\n')
        print(version+': '+json.dumps({k:v for k,v in data.items() if k!='output_bits'}),flush=True)
    assert runs['R08']['output_bits']==runs['R09']['output_bits']==runs['R10']['output_bits']
    old=json.loads((ROOT/'V11_grid_packets/R08_CPU_RESULT.json').read_text(encoding='utf-8'))
    for key,bits in old['output_bits'].items():assert runs['R08']['output_bits'][key]==bits
    a,b=runs['R08']['fixtures']['residual_wide'],runs['R09']['fixtures']['residual_wide']
    assert a['ready']==4*b['ready'] and a['free']==4*b['free']
    for key in a:
        if key not in ['ready','free']:assert a[key]==b[key],key
    for fixture in ['macro_wide','native_wide']:
        assert runs['R08']['fixtures'][fixture]==runs['R09']['fixtures'][fixture]
    assert runs['R08']['peak_arena_bytes']==runs['R09']['peak_arena_bytes']==runs['R10']['peak_arena_bytes']
    assert runs['R08']['mixed_ring_bytes_per_group']==runs['R10']['mixed_ring_bytes_per_group']==[262144,65536,262144,65536]
    assert runs['R09']['mixed_ring_bytes_per_group']==[262144]*4
    negatives={}
    for file,old,new,define,error in [
        ('common_extracted.hpp','if(tileSlot+1==PACKET_TILES)AscendC::CrossCoreSetFlag<0x2,PIPE_MTE2>(FREE+ringSlot);',
         'if(tileSlot==0)AscendC::CrossCoreSetFlag<0x2,PIPE_MTE2>(FREE+ringSlot);',
         'NEGATIVE_RESIDUAL_FREE','ring freed before all published data was read'),
        ('residual_extracted.hpp','if(seq%PACKET_TILES)AscendC::CrossCoreSetFlag<0x2,PIPE_FIX>(READY+((seq/PACKET_TILES)&1));',
         '// Negative control: tail publication removed.',
         'NEGATIVE_RESIDUAL_FLUSH','timeout: unmatched flag / deadlock')]:
        prepare('R09');build.write(BUILD/'source_checks.cpp',harness('R09'))
        path=BUILD/file;good=path.read_text(encoding='utf-8');build.write(path,once(good,old,new))
        exe=BUILD/(define+'.exe')
        try:
            call(args+['-D'+define+'=1','-o',str(exe)],define+'_compile')
            result=call([str(exe)],define+'_run',failure=error)
        finally:build.write(path,good)
        negatives[define]={'rejected':True,'exit_code':result.returncode,'stderr':result.stderr.strip()}
    previous=json.loads((ROOT/'V11_grid_packets/CHECKS.json').read_text(encoding='utf-8'))
    artifacts=dict(previous['artifacts'])
    for rel,digest in artifacts.items():assert build.sha(ROOT/rel)==digest,rel
    for path in [HERE/'build.py',Path(__file__),HERE/'one_wave_plan.asc',HERE/'one_wave_macro_fragment.asc',
                 HERE/'residual_packet_fragment.asc',ROOT/'V11_grid_packets/run_checks.py',
                 ROOT/'V11_grid_packets/R08_CPU_RESULT.json']:
        artifacts[path.relative_to(ROOT).as_posix()]=build.sha(path)
    report={'scope':'actual-source CPU storage/event/ownership model and exact host planner; not hardware timing or TLE certification',
            'sources':{p.name:build.sha(p) for p in build.OUT.glob('*.asc')},'composition':build.verify(),
            'ordinary_outputs_equal_bitwise':True,'known_numerical_limitations_remain':True,
            'negative_controls':negatives,'grid_checks':grid,
            'runs':{k:{kk:vv for kk,vv in v.items() if kk!='output_bits'} for k,v in runs.items()},
            'R07_TLE_root_cause_confirmed':False,'cann_compiled_locally':False,'npu_tested_locally':False,'artifacts':artifacts}
    for path in [HERE/'CHECKS.json',build.OUT/'CPU_CHECKS.json']:build.write(path,json.dumps(report,indent=2)+'\n')
    print('R08/R09/R10 outputs, closed-form work and residual packet negative controls passed.',flush=True)
if __name__=='__main__':main()

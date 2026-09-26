"""Run source-extracted R04/R07/R08 models, exact host-grid audit and packet mutants."""
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
build=load('grid_packet_build',HERE/'build.py')
prior=load('lowlevel_checks',ROOT/'V11_lowlevel/run_checks.py')
prior.BUILD=prior.parent.BUILD=prior.parent.previous.BUILD=prior.parent.previous.parent.BUILD=BUILD
once=build.once;call=prior.call

def prepare(version):
    prior.prepare('R04')
    source=(build.BASE if version=='R04' else build.OUT/(build.NAMES[version]+'.asc')).read_text(encoding='utf-8')
    if version=='R07':
        fragment=(HERE/'r07_macro_fragment.asc').read_text(encoding='utf-8');assert fragment in source
        build.write(BUILD/'ring_extracted.hpp',prior.parent.previous.parent.extract(fragment,'// BMMS11R2_CPU_EXTRACT_END'))
    common=(BUILD/'common_extracted.hpp').read_text(encoding='utf-8')
    if version=='R08':
        original=build.BASE.read_text(encoding='utf-8')
        pp=(HERE/'packet_producer.asc').read_text(encoding='utf-8')
        pc=(HERE/'packet_consumer.asc').read_text(encoding='utf-8')
        nr=(HERE/'native_ring.asc').read_text(encoding='utf-8')
        for part in [pp,pc,nr]:assert part in source
        common=once(common,build.producer(original),pp)
        common=once(common,build.consumer(original),build.consumer(original)+pc)
        common=once(common,build.ring(original),nr)
    else:
        common+='\nnamespace bmms83 {using SmallKPacketConsumer=SmallKConsumer;}\n'
    build.write(BUILD/'common_extracted.hpp',common)

def harness(version):
    s=prior.harness()
    s=once(s,'    Mock::need(lastRingPerGroup==(useMacro?262144:65536),"wrong ring size for selected branch");',
        '    Mock::need(lastRingPerGroup==((useMacro'+('||useSmall' if version=='R08' else '')+')?262144:65536),"wrong ring size for selected branch");')
    s=once(s,'else{bmms83::SmallKConsumer op;runConsumer(op);}',
        '''else if(useSmall){bmms83::SmallKPacketConsumer op;runConsumer(op);}
                else{bmms83::SmallKConsumer op;runConsumer(op);}''')
    if version=='R07':
        s=once(s,'''        Mock::need(p.mTiles==r2.mTiles&&p.nTiles==r2.nTiles&&p.pM==r2.pM&&p.pN==r2.pN&&
            p.tasks==r2.tasks&&p.blocks==r2.blocks,"merged macro plan differs from R01");''',
            '''        Mock::need(p.mTiles==r2.mTiles&&p.nTiles==r2.nTiles&&r2.tasks==B*r2.pM*r2.pN&&
            r2.blocks==p.blocks&&r2.pM>=1&&r2.pM<=r2.mTiles&&r2.pN>=1&&r2.pN<=r2.nTiles,"invalid balanced plan");
        if(p.pM!=r2.pM||p.pN!=r2.pN){auto a=bmms11r2::PeakForGrid(p),b=bmms11r2::PeakForGrid(r2);
            Mock::need(b.tiles*8<=a.tiles*7&&b.cells*8<=a.cells*7&&b.input*8<=a.input*7,"grid margin violated");}''')
    s=once(s,'    guards();', '''#ifdef NEGATIVE_PACKET_FREE
    dense<half,false,false>(1,64,512,32,1,0,false);return 7;
#endif
#ifdef NEGATIVE_PACKET_FLUSH
    dense<half,false,false>(1,16,384,128,1,0,false);return 7;
#endif
    guards();''')
    s=once(s,'    std::ostringstream fixtures;', '''    for(int rev=0;rev<2;++rev){
        for(auto d:std::vector<std::array<int,5>>{
            {1,16,128,32,1},{1,16,256,64,1},{1,16,384,128,1},
            {1,64,640,64,1},{1,144,1040,32,1},{3,80,144,64,2}}){
            layouts<half>(d,0,rev);layouts<bfloat16_t>(d,0,rev);
        }
        dense<half,false,true>(1,384,768,256,5,0,rev);
        dense<bfloat16_t,true,false>(3,144,528,256,4,1,rev);
    }
    std::ostringstream fixtures;''')
    return s

def grid_check(compiler):
    old=(ROOT/'V11_followup/macro_ring_fragment.asc').read_text(encoding='utf-8')
    new=(HERE/'r07_macro_fragment.asc').read_text(encoding='utf-8')
    source=(HERE/'grid_checks.cpp.in').read_text(encoding='utf-8')
    parts=[]
    for name,fragment in [('baseline',old),('candidate',new)]:
        body=build.between(fragment,'namespace bmms11r2 {','static inline uint64_t RingBytes(')
        parts.append(body.replace('namespace bmms11r2 {','namespace '+name+' {',1)+'}\n')
    build.write(BUILD/'grid_checks.cpp',once(source,'// INSERT_PLANS','\n'.join(parts)))
    exe=BUILD/('grid_checks.exe' if os.name=='nt' else 'grid_checks')
    call([compiler,'-std=c++20','-O2','grid_checks.cpp','-o',str(exe)],'grid_compile')
    data=json.loads(call([str(exe)],'grid_run').stdout)
    assert data['checked']>2000 and data['changed']>0
    build.write(HERE/'GRID_CHECKS.json',json.dumps(data,indent=2)+'\n')
    print('Grid: '+json.dumps(data),flush=True);return data

def main():
    build.verify();prepare('R04')
    compiler=shutil.which(os.environ.get('CXX','g++'))
    if not compiler:raise RuntimeError('g++ required')
    grid=grid_check(compiler)
    runs={}
    args=[compiler,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-pthread',
          '-DCHECK_R01=1','-DCHECK_R04=1','source_checks.cpp']
    for version in ['R04','R07','R08']:
        prepare(version);build.write(BUILD/'source_checks.cpp',harness(version))
        exe=BUILD/(version+('.exe' if os.name=='nt' else ''))
        call(args+['-o',str(exe)],version+'_compile')
        data=json.loads(call([str(exe)],version+'_run').stdout);runs[version]=data
        assert data['strict_misses']==data['combined_misses']==0 and data['known_precision_limitations']==3
        assert data['source_runs']==356 and data['repeat_pairs']==178
        build.write(HERE/(version+'_CPU_RESULT.json'),json.dumps(data,indent=2)+'\n')
        print(version+': '+json.dumps({k:v for k,v in data.items() if k!='output_bits'}),flush=True)
    assert runs['R04']['output_bits']==runs['R07']['output_bits']==runs['R08']['output_bits']
    old=json.loads((ROOT/'V11_lowlevel/R04_CPU_RESULT.json').read_text(encoding='utf-8'))
    for key,bits in old['output_bits'].items():assert bits==runs['R04']['output_bits'][key]
    before,after=runs['R04']['fixtures']['native_wide'],runs['R08']['fixtures']['native_wide']
    assert before['ready']==4*after['ready'] and before['free']==4*after['free']
    for key in before:
        if key not in ['ready','free']:assert before[key]==after[key],key
    for name in ['macro_wide','residual_wide']:
        assert runs['R04']['fixtures'][name]==runs['R08']['fixtures'][name]
    assert runs['R04']['peak_arena_bytes']==runs['R08']['peak_arena_bytes']==runs['R07']['peak_arena_bytes']
    negatives={}
    for old,new,define,message in [
        ('if(tileSlot+1==PACKET_TILES)AscendC::CrossCoreSetFlag<0x2,PIPE_MTE2>(FREE+ringSlot);',
         'if(tileSlot==0)AscendC::CrossCoreSetFlag<0x2,PIPE_MTE2>(FREE+ringSlot);',
         'NEGATIVE_PACKET_FREE','ring freed before all published data was read'),
        ('if(seq%PACKET_TILES)AscendC::CrossCoreSetFlag<0x2,PIPE_FIX>(READY+((seq/PACKET_TILES)&1));',
         '// NEGATIVE: missing final partial packet publication',
         'NEGATIVE_PACKET_FLUSH','timeout: unmatched flag / deadlock')]:
        prepare('R08');build.write(BUILD/'source_checks.cpp',harness('R08'))
        path=BUILD/'common_extracted.hpp';good=path.read_text(encoding='utf-8')
        build.write(path,once(good,old,new));exe=BUILD/(define+('.exe' if os.name=='nt' else ''))
        try:
            call(args+['-D'+define+'=1','-o',str(exe)],define+'_compile')
            result=call([str(exe)],define+'_run',failure=message)
        finally:build.write(path,good)
        negatives[define]={'rejected':True,'exit_code':result.returncode,'stderr':result.stderr.strip()}
    previous=json.loads((ROOT/'V11_lowlevel/CHECKS.json').read_text(encoding='utf-8'))
    artifacts=dict(previous['artifacts'])
    for rel,digest in artifacts.items():assert build.sha(ROOT/rel)==digest,rel
    for p in [HERE/'build.py',Path(__file__),HERE/'balanced_plan.asc',HERE/'r07_macro_fragment.asc',
              HERE/'native_ring.asc',HERE/'packet_producer.asc',HERE/'packet_consumer.asc',HERE/'grid_checks.cpp.in',
              ROOT/'V11_lowlevel/R04_CPU_RESULT.json']:
        artifacts[p.relative_to(ROOT).as_posix()]=build.sha(p)
    report={'scope':'actual-source CPU storage/event/ownership model and exact host workload; not hardware timing',
        'sources':{p.name:build.sha(p) for p in build.OUT.glob('*.asc')},'composition':build.verify(),
        'ordinary_outputs_equal_bitwise':True,'known_numerical_limitations_remain':True,
        'negative_controls':negatives,'grid_checks':grid,
        'runs':{k:{kk:vv for kk,vv in v.items() if kk!='output_bits'} for k,v in runs.items()},
        'cann_compiled_locally':False,'npu_tested_locally':False,'artifacts':artifacts}
    for p in [HERE/'CHECKS.json',build.OUT/'CPU_CHECKS.json']:build.write(p,json.dumps(report,indent=2)+'\n')
    print('Exact grid coverage, three-version outputs and packet negative controls passed.',flush=True)

if __name__=='__main__':main()

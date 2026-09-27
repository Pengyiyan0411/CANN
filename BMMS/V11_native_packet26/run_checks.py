"""Replay actual R25/R26 producers and consumers, with packet fault controls."""
from pathlib import Path
import importlib.util,json,shutil,subprocess,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;BUILD=HERE/'cpu_build'
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
b=load('packet_builder',HERE/'build.py');prior=load('targeted_checks26',ROOT/'V11_native_targeted25/run_checks.py')
prior.BUILD=BUILD;prior.old.BUILD=BUILD;prior.old.native.BUILD=BUILD;prior.old.native.previous.BUILD=BUILD
prior.old.native.previous.flex.BUILD=BUILD;prior.old.native.previous.flex.redirect(prior.old.native.previous.flex.prior)
def prepare():
    prior.prepare()
    src=(b.OUT/(b.NAME+'.asc')).read_text(encoding='utf-8')
    b.write(BUILD/'packet_extracted.hpp',b.between(src,'// BMMS26_BEGIN','// BMMS26_CPU_EXTRACT_END'))
    shim=(BUILD/'cpu_shim.hpp').read_text(encoding='utf-8')
    shim=b.once(shim,'uint64_t readyCount=0,freeCount=0,readElements=0,writeElements=0;',
        'uint64_t readyCount=0,freeCount=0,readElements=0,writeElements=0,dmaCalls=0;')
    shim=b.once(shim,'s.reads[Mock::subId]+=elements;readElements+=elements;',
        's.reads[Mock::subId]+=elements;readElements+=elements;++dmaCalls;')
    b.write(BUILD/'cpu_shim.hpp',shim)
    h=(ROOT/'V11_native_targeted25/source_checks.cpp.in').read_text(encoding='utf-8')
    h=b.once(h,'#include "targeted_extracted.hpp"','#include "targeted_extracted.hpp"\n#include "packet_extracted.hpp"')
    old='if(strategy==2){bmms25::Entry<T,TA,TB,false>((GM_ADDR)a.data(),(GM_ADDR)b.data(),(GM_ADDR)y.data(),(GM_ADDR)ws.data(),(GM_ADDR)part,p);return;}'
    new='''if(strategy==2){
#if PACKET
                bmms26::Entry<T,TA,TB>((GM_ADDR)a.data(),(GM_ADDR)b.data(),(GM_ADDR)y.data(),(GM_ADDR)ws.data(),(GM_ADDR)part,p);
#else
                bmms25::Entry<T,TA,TB,false>((GM_ADDR)a.data(),(GM_ADDR)b.data(),(GM_ADDR)y.data(),(GM_ADDR)ws.data(),(GM_ADDR)part,p);
#endif
                return;}
'''
    h=b.once(h,old,new)
    h=b.once(h,'<<",\\\"ready\\\":"<<ring.readyCount',
        '<<",\\\"C_DMA_calls\\\":"<<ring.dmaCalls<<",\\\"ready\\\":"<<ring.readyCount')
    h=b.once(h,'#ifdef NEGATIVE_SMALL', '''#ifdef NEGATIVE_PACKET
    run<half,false,false>(1,256,2048,128,3,0,false);return misses?2:7;
#endif
#ifdef NEGATIVE_TAIL
    run<half,false,false>(1,80,656,128,3,1,false);return misses?2:7;
#endif
#ifdef NEGATIVE_SMALL''')
    h=b.once(h,'        // Native shapes outside the two predicates retain the original consumer.', '''        // Many packets, final 1/2/3-tile packets, task/panel/M-stage boundaries,
        // and ragged M/N. Exercise the look-ahead independently of the baseline plan.
        for(auto mn:std::vector<std::array<int,2>>{{256,2048},{768,528},{80,656},{144,784},{272,1040},{48,1664}}){
            layouts<half>(1,mn[0],mn[1],128,3,0,rev);
            layouts<bfloat16_t>(1,mn[0],mn[1],128,3,3,rev);
        }
        // Native shapes outside the two predicates retain the original consumer.''')
    b.write(HERE/'source_checks.cpp.in',h);b.write(BUILD/'source_checks.cpp',h)
def call(args,stem,error=None):
    p=subprocess.run(args,cwd=BUILD,capture_output=True,text=True,timeout=600)
    b.write(BUILD/(stem+'.stdout.txt'),p.stdout);b.write(BUILD/(stem+'.stderr.txt'),p.stderr)
    if error:
        allowed=(error,) if isinstance(error,str) else error
        assert p.returncode and any(e in p.stderr for e in allowed),(stem,p.returncode,p.stderr[-2500:])
    elif p.returncode:raise RuntimeError(stem+': '+p.stderr[-3000:]+p.stdout[-500:])
    return p
def main():
    b.verify();BUILD.mkdir(exist_ok=True);prepare();compiler=shutil.which('g++');assert compiler
    args=[compiler,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-pthread','-DCHECK_R01=1','-DTARGETED=1','source_checks.cpp']
    runs={}
    for name,mode in [('R25',0),('R26',1)]:
        exe=BUILD/(name+'.exe');call(args+['-DPACKET='+str(mode),'-o',str(exe)],name+'_compile')
        data=json.loads(call([str(exe)],name+'_run').stdout);runs[name]=data;assert data['strict_misses']==0
        b.write(HERE/(name+'_CPU_RESULT.json'),json.dumps(data,indent=2)+'\n')
        print(name+': '+json.dumps({k:v for k,v in data.items() if k not in ['output_bits','fixtures']}),flush=True)
    assert runs['R25']['output_bits']==runs['R26']['output_bits']
    improved=0
    for key,before in runs['R25']['fixtures'].items():
        after=runs['R26']['fixtures'][key]
        for field in ['pM','pN','blocks','barriers','partial_dma_calls','partial_read_elements','partial_write_elements','ready','free','mmads']:
            assert after[field]==before[field],(key,field)
        assert after['C_DMA_calls']<=before['C_DMA_calls'];assert after['duplicate_elements']<=before['duplicate_elements']
        improved+=after['C_DMA_calls']<before['C_DMA_calls']
        if not key.startswith('f1600_1_'):assert before==after,('non-dense work changed',key)
    assert improved>0
    faults={}
    for name,a,z,define,error in [
        ('BAD_PACKET_STRIDE','uint32_t((TM*TN-vr*TN)*4)','uint32_t(0)','NEGATIVE_PACKET',('uninitialised','uninitialized','STRUCTURAL_FAIL')),
        ('NO_TAIL_FILL','if(nr[i]<TN)AscendC::Duplicate','if(false)AscendC::Duplicate','NEGATIVE_TAIL',('uninitialised','uninitialized','STRUCTURAL_FAIL')),
        ('EARLY_FREE','auto data=workBuf.Get<float>();','AscendC::CrossCoreSetFlag<0x2,PIPE_MTE2>(FREE+ringSlot);\n        auto data=workBuf.Get<float>();','NEGATIVE_PACKET','ring freed before all published data was read')]:
        path=BUILD/'packet_extracted.hpp';good=path.read_text(encoding='utf-8');b.write(path,b.once(good,a,z))
        try:
            exe=BUILD/(name+'.exe');call(args+['-DPACKET=1','-D'+define+'=1','-o',str(exe)],name+'_compile')
            # Wrong packed source stride can yield a precise-but-wrong finite result,
            # which the harness reports by exit code 2 rather than an exception.
            if name=='BAD_PACKET_STRIDE':
                bad=subprocess.run([str(exe)],cwd=BUILD,capture_output=True,text=True,timeout=600)
                b.write(BUILD/(name+'_run.stdout.txt'),bad.stdout);b.write(BUILD/(name+'_run.stderr.txt'),bad.stderr)
                assert bad.returncode in [1,2] and (bad.returncode==2 or 'STRUCTURAL_FAIL' in bad.stderr),(name,bad.returncode,bad.stderr)
            else:bad=call([str(exe)],name+'_run',error)
            faults[name]={'rejected':True,'exit_code':bad.returncode,'stderr':bad.stderr.strip()}
        finally:b.write(path,good)
        print(name+': rejected',flush=True)
    report=dict(scope='actual-source CPU memory/layout/ownership/ordinary precision and logical work, not CANN/NPU',
        sources={p.name:b.sha(p) for p in b.OUT.glob('*.asc')},composition=b.verify(),ordinary_outputs_equal_R25_bitwise=True,
        unchanged_small_branch_logical_work=True,negative_controls=faults,dense_fixtures_with_fewer_C_DMA_calls=improved,
        runs={n:{k:v for k,v in d.items() if k!='output_bits'} for n,d in runs.items()},
        artifacts={p.relative_to(ROOT).as_posix():b.sha(p) for p in HERE.iterdir() if p.is_file() and p.suffix in ['.py','.asc','.in']},
        harness_headers={p.name:b.sha(p) for p in BUILD.glob('*.hpp')},cann_compiled_locally=False,npu_tested_locally=False,full_domain_precision_proven=False)
    for p in [HERE/'CHECKS.json',b.OUT/'CPU_CHECKS.json']:b.write(p,json.dumps(report,indent=2)+'\n')
    print('R25/R26 source replay and fault controls passed.',flush=True)
if __name__=='__main__':main()

"""Actual R25/R27 source replay + independent full-tile UnitFlag contract checks."""
from pathlib import Path
import importlib.util,json,shutil,subprocess,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;BUILD=HERE/'cpu_build'

def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
b=load('unit_builder',HERE/'build.py');prior=load('targeted_checks27',ROOT/'V11_native_targeted25/run_checks.py')
prior.BUILD=BUILD;prior.old.BUILD=BUILD;prior.old.native.BUILD=BUILD;prior.old.native.previous.BUILD=BUILD
prior.old.native.previous.flex.BUILD=BUILD;prior.old.native.previous.flex.redirect(prior.old.native.previous.flex.prior)

def prepare():
    prior.prepare()
    src=(b.OUT/(b.NAME+'.asc')).read_text(encoding='utf-8')
    b.write(BUILD/'unit_extracted.hpp',b.between(src,'// BMMS27_BEGIN','// BMMS27_CPU_EXTRACT_END'))
    shim=(BUILD/'cpu_shim.hpp').read_text(encoding='utf-8')
    shim=b.once(shim,'namespace AscendC {\nenum class TPosition', '''namespace UnitStats {
inline std::atomic<uint64_t> mmads{0},fixes{0},mFixWaits{0};
inline void reset(){mmads=0;fixes=0;mFixWaits=0;}
}
namespace AscendC {
enum class TPosition''')
    shim=b.once(shim,'if constexpr(E==HardEvent::M_FIX)Mock::smallMmadPending=false;',
        'if constexpr(E==HardEvent::M_FIX){Mock::smallMmadPending=false;++UnitStats::mFixWaits;}')
    shim=b.once(shim,'uint64_t readyCount=0,freeCount=0,readElements=0,writeElements=0;',
        'uint64_t readyCount=0,freeCount=0,readElements=0,writeElements=0,dmaCalls=0;')
    shim=b.once(shim,'s.reads[Mock::subId]+=elements;readElements+=elements;',
        's.reads[Mock::subId]+=elements;readElements+=elements;++dmaCalls;')
    b.write(BUILD/'cpu_shim.hpp',shim)
    model=(BUILD/'cube_model.hpp').read_text(encoding='utf-8')
    model=b.once(model,'enum class QuantMode_t { NoQuant };',(HERE/'unit_contract.hpp').read_text(encoding='utf-8')+'\nenum class QuantMode_t { NoQuant };')
    model=b.once(model,'struct MmadParams { int m=0,n=0,k=0;', 'struct MmadParams { int unitFlag=0; int m=0,n=0,k=0;')
    model=b.once(model,'struct FixpipeParamsV220 {','inline void SetMMRowMajor(){UnitContract::rowMajor=true;}\ninline void SetMMColumnMajor(){UnitContract::rowMajor=false;}\nstruct FixpipeParamsV220 {\n    int unitFlag=0;')
    model=b.once(model,'    std::vector<float> av(p.m*p.k),bv(p.k*p.n);',
        '    UnitContract::beforeMmad(c.b.get(),c.offset,p.m,p.n,p.unitFlag,p.cmatrixInitVal);\n    std::vector<float> av(p.m*p.k),bv(p.k*p.n);')
    model=b.once(model,'    SplitAudit::write(d.p,p.mSize,p.nSize);',
        '    UnitContract::beforeFix(s.b.get(),s.offset,p.mSize,p.nSize,p.srcStride,p.ndNum,p.unitFlag);\n    SplitAudit::write(d.p,p.mSize,p.nSize);')
    b.write(BUILD/'cube_model.hpp',model)
    # Reuse the broad fixture inventory (not R26's producer/consumer).
    h=(ROOT/'V11_native_packet26/source_checks.cpp.in').read_text(encoding='utf-8')
    h=h.replace('packet_extracted.hpp','unit_extracted.hpp').replace('#if PACKET','#if UNIT').replace('bmms26::Entry','bmms27::Entry')
    h=b.once(h,'Mock::localFlags={};Mock::smallMmadPending=false;fn(w);',
        'Mock::localFlags={};Mock::smallMmadPending=false;UnitContract::reset();fn(w);UnitContract::drained();\n            Mock::need(!Mock::smallMmadPending,"small MMAD missing final dependency");')
    h=b.once(h,'Traffic::reset();NativeTraffic::reset();OpStats::reset();',
        'Traffic::reset();NativeTraffic::reset();OpStats::reset();UnitStats::reset();')
    h=b.once(h,'        flags.drained();ring.drained();', '''        flags.drained();ring.drained();
        const bool unitActive=UNIT&&strategy==2;
        Mock::need(UnitStats::mmads==(unitActive?Traffic::mmads.load():0),"wrong UnitFlag MMAD count");
        Mock::need(UnitStats::fixes==UnitStats::mmads,"unpaired UnitFlag operation count");
        Mock::need(UnitStats::mFixWaits==(unitActive?0:Traffic::mmads.load()),"wrong whole-tile M_FIX wait count");''')
    h=b.once(h,'<<",\\\"C_DMA_calls\\\":"<<ring.dmaCalls',
        '<<",\\\"unit_mmads\\\":"<<UnitStats::mmads<<",\\\"unit_fixes\\\":"<<UnitStats::fixes<<",\\\"M_FIX_waits\\\":"<<UnitStats::mFixWaits<<",\\\"C_DMA_calls\\\":"<<ring.dmaCalls')
    lo=h.index('#ifdef NEGATIVE_PACKET');hi=h.index('#ifdef NEGATIVE_SMALL',lo)
    h=h[:lo]+'''#ifdef NEGATIVE_UNIT
    run<half,false,false>(1,144,784,128,3,0,false);return misses?2:7;
#endif
#ifdef NEGATIVE_SMALL_MMAD
    run<half,false,false>(1,48,144,128,3,0,false);return misses?2:7;
#endif
'''+h[hi:]
    h=h.replace('// and ragged M/N. Exercise the look-ahead independently of the baseline plan.',
        '// and ragged M/N. Exercise both L0C slots and UnitFlag resets across boundaries.')
    b.write(HERE/'source_checks.cpp.in',h);b.write(BUILD/'source_checks.cpp',h)

def call(args,stem,error=None):
    p=subprocess.run(args,cwd=BUILD,capture_output=True,text=True,timeout=600)
    b.write(BUILD/(stem+'.stdout.txt'),p.stdout);b.write(BUILD/(stem+'.stderr.txt'),p.stderr)
    if error:assert p.returncode and error in p.stderr,(stem,p.returncode,p.stderr[-2500:])
    elif p.returncode:raise RuntimeError(stem+': '+p.stderr[-3000:]+p.stdout[-500:])
    return p

def main():
    b.verify();BUILD.mkdir(exist_ok=True);prepare();compiler=shutil.which('g++');assert compiler
    args=[compiler,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-pthread','-DCHECK_R01=1','-DTARGETED=1','source_checks.cpp']
    runs={}
    for name,mode in [('R25',0),('R27',1)]:
        exe=BUILD/(name+'.exe');call(args+['-DUNIT='+str(mode),'-o',str(exe)],name+'_compile')
        data=json.loads(call([str(exe)],name+'_run').stdout);runs[name]=data;assert data['strict_misses']==0
        b.write(HERE/(name+'_CPU_RESULT.json'),json.dumps(data,indent=2)+'\n')
        print(name+': '+json.dumps({k:v for k,v in data.items() if k not in ['output_bits','fixtures']}),flush=True)
    assert runs['R25']['output_bits']==runs['R27']['output_bits']
    assert runs['R25']['arena_peaks']==runs['R27']['arena_peaks']
    for key,old in runs['R25']['fixtures'].items():
        new=runs['R27']['fixtures'][key]
        filtered=lambda d:{k:v for k,v in d.items() if k not in ['unit_mmads','unit_fixes','M_FIX_waits']}
        assert filtered(old)==filtered(new),(key,old,new)
        if key.split('_')[1]!='1':assert old==new,(key,old,new)
    path=BUILD/'unit_extracted.hpp';good=path.read_text(encoding='utf-8');faults={}
    for name,old,new,define,error in [
        ('MISSING_MMAD_FLAG','q.unitFlag=3;','q.unitFlag=0;','NEGATIVE_UNIT','UnitFlag FIX without matching MMAD flag'),
        ('MISSING_FIX_FLAG','f.unitFlag=3;','f.unitFlag=0;','NEGATIVE_UNIT','UnitFlag MMAD without matching FIX flag'),
        ('PARTIAL_FIX','f.mSize=mr;','f.mSize=mr/2;','NEGATIVE_UNIT','UnitFlag incomplete full-tile consumption'),
        ('MISSING_SMALL_DEPENDENCY','if((mr/16)*(nr/16)<10)AscendC::PipeBarrier<PIPE_M>();','/* missing */','NEGATIVE_SMALL_MMAD','small MMAD missing'),
    ]:
        try:
            b.write(path,b.once(good,old,new));exe=BUILD/(name+'.exe')
            call(args+['-DUNIT=1','-D'+define+'=1','-o',str(exe)],name+'_compile')
            result=call([str(exe)],name+'_run',error)
            faults[name]=dict(rejected=True,exit_code=result.returncode,stderr=result.stderr.strip())
        finally:b.write(path,good)
        print(name+': rejected',flush=True)
    report=dict(scope='actual-source CPU layout/arithmetic/ownership checks and full-tile UnitFlag contract; not device scheduling or CANN compilation',
        sources={p.name:b.sha(p) for p in b.OUT.glob('*.asc')},composition=b.verify(),ordinary_outputs_equal_R25_bitwise=True,
        all_data_work_and_resources_equal_R25=True,unchanged_small_branch_logical_work=True,negative_controls=faults,
        runs={n:{k:v for k,v in d.items() if k!='output_bits'} for n,d in runs.items()},
        artifacts={p.relative_to(ROOT).as_posix():b.sha(p) for p in HERE.iterdir() if p.is_file() and p.suffix in ['.py','.asc','.in','.hpp']},
        harness_headers={p.name:b.sha(p) for p in BUILD.glob('*.hpp')},cann_compiled_locally=False,npu_tested_locally=False,full_domain_precision_proven=False)
    for p in [HERE/'CHECKS.json',b.OUT/'CPU_CHECKS.json']:b.write(p,json.dumps(report,indent=2)+'\n')
    print('R25/R27 source replay and fault controls passed.',flush=True)
if __name__=='__main__':main()

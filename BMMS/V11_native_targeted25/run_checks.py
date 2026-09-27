"""Actual-source CPU replay, packet ownership, merge coverage, and fault controls."""
from pathlib import Path
import importlib.util,json,shutil,subprocess,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;BUILD=HERE/'cpu_build'
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
b=load('targeted_builder',HERE/'build.py');old=load('split_checks25',ROOT/'V11_split_k/run_checks.py')
old.BUILD=BUILD;old.native.BUILD=BUILD;old.native.previous.BUILD=BUILD;old.native.previous.flex.BUILD=BUILD;old.native.previous.flex.redirect(old.native.previous.flex.prior)

def prepare():
    old.prepare()
    source=(b.OUT/'R25_NATIVE_TARGETED.asc').read_text(encoding='utf-8')
    frag=b.between(source,'// BMMS25_BEGIN','// BMMS25_CPU_EXTRACT_END')
    b.write(BUILD/'targeted_extracted.hpp','#define BMMS25_SMALL 1\n#define BMMS25_DENSE 1\n#define ASCEND_IS_AIC (Mock::cube)\n#define ASCEND_IS_AIV (!Mock::cube)\n'+frag)
    shim=(BUILD/'cpu_shim.hpp').read_text(encoding='utf-8')
    # Extend the ownership oracle for whole-tile ownership. Old row-half mode is unchanged.
    shim=b.once(shim,'bool published=false;uint64_t writes=0,reads[2]={0,0};bool freed[2]={false,false};',
        'bool published=false;uint64_t writes=0,reads[2]={0,0};bool freed[2]={false,false};unsigned tileMask[2]={0,0};')
    shim=b.once(shim,'uintptr_t base;size_t bytes,slotBytes;','uintptr_t base;size_t bytes,slotBytes;int wholeTileElements=0;')
    shim=b.once(shim,'Mock::need(s.reads[Mock::subId]<=s.writes/2,"consumer reads more than its published half");',r'''
        if(wholeTileElements){
            const int tile=(uintptr_t(ptr)-base-size_t(i)*slotBytes)/(64*128*4);
            Mock::need(elements==wholeTileElements&&tile%2==Mock::subId,"wrong whole-tile consumer owner");
            Mock::need(!(s.tileMask[Mock::subId]&(1u<<tile)),"whole tile read twice");
            s.tileMask[Mock::subId]|=1u<<tile;
        }else Mock::need(s.reads[Mock::subId]<=s.writes/2,"consumer reads more than its published half");''')
    shim=b.once(shim,'Mock::need(s.reads[Mock::subId]==s.writes/2,"ring freed before all published data was read");',r'''
        const uint64_t expected=wholeTileElements?
            ((s.writes/wholeTileElements+1-Mock::subId)/2)*wholeTileElements:s.writes/2;
        Mock::need(s.reads[Mock::subId]==expected,"ring freed before all published data was read");''')
    # Track actual partial memory transactions and require the publication barrier.
    shim=b.once(shim,'namespace AscendC {\nenum class TPosition',r'''
namespace TargetAudit {
inline uintptr_t partial=0;inline size_t elements=0;
inline std::atomic<uint64_t> dmaCalls{0},reads{0},writes{0};
inline std::vector<unsigned> visits;
inline void begin(float* p,size_t n){partial=(uintptr_t)p;elements=n;dmaCalls=0;reads=0;writes=0;visits.assign(n,0);}
inline bool inside(uintptr_t p){return p>=partial&&p<partial+elements*4;}
inline void dma(uintptr_t p){if(inside(p))++dmaCalls;}
inline void read(uintptr_t p){if(inside(p)){
    Mock::need(Mock::ctx->barrier.generation==1,"partial read before original barrier");
    ++reads;++visits[(p-partial)/4];}}
inline void write(uintptr_t p){if(inside(p))++writes;}
}
namespace AscendC {
enum class TPosition''')
    shim=b.once(shim,'ReductionAudit::read((uintptr_t)(p+i));','ReductionAudit::read((uintptr_t)(p+i));TargetAudit::read((uintptr_t)(p+i));')
    shim=b.once(shim,'ReductionAudit::write((uintptr_t)(p+i));','ReductionAudit::write((uintptr_t)(p+i));TargetAudit::write((uintptr_t)(p+i));')
    # The two DataCopy overloads have identical bodies; replace the complete GM->UB signature.
    marker='template<class T>void DataCopy(LocalTensor<T>d,GlobalTensor<T>s,int n){'
    shim=b.once(shim,marker,marker+'TargetAudit::dma((uintptr_t)s.p);')
    marker='template<class T>void DataCopyPad(LocalTensor<T>d,GlobalTensor<T>s,DataCopyExtParams cp,DataCopyPadExtParams<T> pad){'
    shim=b.once(shim,marker,marker+'TargetAudit::dma((uintptr_t)s.p);')
    b.write(BUILD/'cpu_shim.hpp',shim)
    # Extract exactly the old/new merge tail into a standalone capacity/stride test.
    orig=b.BASE.read_text(encoding='utf-8')
    cons=b.between(orig,'class SmallKPacketConsumer {','template<class T,bool TA,bool TB,int TK>\n__aicore__ inline void NativeEntry(')
    tail=cons[cons.index('        auto merged=mergedBuf.Get<float>(),tmp=tmpBuf.Get<float>();'):]
    tail=tail[:-len('    }\n};\n\n')]
    new=(HERE/'dense_merge.asc').read_text(encoding='utf-8')
    helper='''using namespace bmms83;
void isolatedMerge(const NativePlan& p,float* partial,float* output,AscendC::TPipe& pipe,bool candidate){
    AscendC::TPipe* pipe_=&pipe;const int worker=0;
    AscendC::GlobalTensor<float> part,out;part.SetGlobalBuffer(partial,p.M*p.pN);out.SetGlobalBuffer(output,1);
    AscendC::TBuf<AscendC::TPosition::VECIN> mergedBuf,tmpBuf;
    AscendC::TBuf<AscendC::TPosition::VECCALC> sumBuf;
    AscendC::TQue<AscendC::TPosition::VECOUT,1> oq;
    const int mergeRows=MinI(p.M,(16384/p.pN/16)*16);
    pipe.InitBuffer(mergedBuf,p.M*4);pipe.InitBuffer(tmpBuf,(candidate?mergeRows*p.pN:p.M)*4);
    pipe.InitBuffer(sumBuf,p.M*4);pipe.InitBuffer(oq,1,32);
    if(candidate){\n'''+new+'\n    }else{\n'+tail+'\n    }\n}\n'
    b.write(BUILD/'isolated_merge.hpp',helper)

def call(args,stem,error=None):
    p=subprocess.run(args,cwd=BUILD,capture_output=True,text=True,timeout=600)
    b.write(BUILD/(stem+'.stdout.txt'),p.stdout);b.write(BUILD/(stem+'.stderr.txt'),p.stderr)
    if error:
        allowed=(error,) if isinstance(error,str) else error
        assert p.returncode and any(e in p.stderr for e in allowed),(stem,p.returncode,p.stderr[-2500:])
    elif p.returncode:raise RuntimeError(stem+': '+p.stderr[-3000:]+p.stdout[-500:])
    return p

def main():
    b.verify();BUILD.mkdir(exist_ok=True);compiler=shutil.which('g++');assert compiler
    prepare();harness=(HERE/'source_checks.cpp.in').read_text(encoding='utf-8');b.write(BUILD/'source_checks.cpp',harness)
    args=[compiler,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-pthread','-DCHECK_R01=1','source_checks.cpp']
    runs={};stamps={}
    for name,mode in [('R23',0),('R25',1)]:
        exe=BUILD/(name+'.exe');call(args+['-DTARGETED='+str(mode),'-o',str(exe)],name+'_compile')
        data=json.loads(call([str(exe)],name+'_run').stdout);runs[name]=data
        assert data['strict_misses']==0
        b.write(HERE/(name+'_CPU_RESULT.json'),json.dumps(data,indent=2)+'\n')
        print(name+': '+json.dumps({k:v for k,v in data.items() if k not in ['output_bits','fixtures']}),flush=True)
    assert runs['R23']['output_bits']==runs['R25']['output_bits']
    faults={}
    for name,file,a,z,define,error in [
        ('SMALL_OWNER','targeted_extracted.hpp','if(sub==(seq&1)){','if(sub==0){','NEGATIVE_SMALL',('wrong whole-tile consumer owner','ring freed before all published data was read')),
        ('DENSE_DROP_ODD','isolated_merge.hpp','keep=active-pairs;','keep=pairs;','NEGATIVE_DENSE','isolated N merge output mismatch')]:
        path=BUILD/file;good=path.read_text(encoding='utf-8');b.write(path,b.once(good,a,z))
        try:
            exe=BUILD/(name+'.exe');call(args+['-DTARGETED=1','-D'+define+'=1','-o',str(exe)],name+'_compile')
            bad=call([str(exe)],name+'_run',error);faults[name]={'rejected':True,'stderr':bad.stderr.strip()}
        finally:b.write(path,good)
        print(name+': rejected',flush=True)
    artifacts={p.relative_to(ROOT).as_posix():b.sha(p) for p in HERE.iterdir() if p.is_file() and p.suffix in ['.py','.asc','.in']}
    report={'scope':'actual-source CPU memory/layout/ownership/precision and logical-work model; no CANN or NPU execution',
        'source_files':{p.name:b.sha(p) for p in b.OUT.glob('*.asc')},'composition':b.verify(),
        'ordinary_outputs_equal_R23_bitwise':True,'negative_controls':faults,
        'runs':{n:{k:v for k,v in d.items() if k!='output_bits'} for n,d in runs.items()},
        'artifacts':artifacts,'harness_headers':{p.name:b.sha(p) for p in BUILD.glob('*.hpp')},
        'inherited_model':'V11_split_k/run_checks.py and its hash-bound predecessors',
        'cann_compiled_locally':False,'npu_tested_locally':False,'full_domain_precision_proven':False}
    for p in [HERE/'CHECKS.json',b.OUT/'CPU_CHECKS.json']:b.write(p,json.dumps(report,indent=2)+'\n')
    print('Source replay and fault controls passed.',flush=True)
if __name__=='__main__':main()

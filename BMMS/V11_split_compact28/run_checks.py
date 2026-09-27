"""Compare actual compact Cube/Vector source with frozen R25, using CPU models.

All inherited generators are redirected into this version's build directory.
No timing produced by this model is an NPU performance measurement.
"""
from pathlib import Path
import importlib.util,json,shutil,subprocess,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;BUILD=HERE/'cpu_build'

def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
b=load('compact_builder',HERE/'build.py')
old=load('compact_inherited_checks',ROOT/'V11_split_k/run_checks.py')
once=b.once

def prepare():
    old.BUILD=BUILD;old.native.BUILD=BUILD;old.native.previous.BUILD=BUILD
    old.native.previous.flex.BUILD=BUILD;old.native.previous.flex.redirect(old.native.previous.flex.prior)
    old.prepare()
    # Verify the complete regenerated inherited model, not just filenames.
    expected=json.loads((ROOT/'V11_split_k/R23_INPUTS.json').read_text())['headers']
    for name,digest in expected.items():assert b.sha(BUILD/name)==digest,name
    base=b.BASE.read_text(encoding='utf-8')
    inherited=(BUILD/'split_extracted.hpp').read_text(encoding='utf-8')
    assert inherited.strip() in base
    source=(b.OUT/(b.NAME+'.asc')).read_text(encoding='utf-8')
    fragment=b.fragment(base);assert fragment in source
    b.write(BUILD/'compact_extracted.hpp',fragment.split('// BMMS28_CPU_EXTRACT_END')[0])
    audit=(ROOT/'V11_split_k/publication_audit.hpp').read_text(encoding='utf-8')
    revised=once(audit,'std::mutex mutex;uint64_t writes=0,totalReads=0;',
        'std::mutex mutex;bool compact;uint64_t writes=0,totalReads=0,dmaCalls=0;')
    revised=once(revised,'int s,int groups):','int s,int groups,bool dense=false):')
    revised=once(revised,'waited(2*groups,0){}','waited(2*groups,0),compact(dense){}')
    revised=once(revised,'void write(void* ptr,int mr,int nr){','void write(void* ptr,int mr,int nr,int pitch){')
    revised=once(revised,'        writes+=uint64_t(mr)*nr;',
        '        Mock::need(pitch==(compact?N:128),"split write pitch mismatch");\n        writes+=uint64_t(mr)*nr;')
    revised=once(revised,'        for(int r=0;r<rows;++r)', '        ++dmaCalls;\n        for(int r=0;r<rows;++r)')
    revised=once(revised,'cell/128<std::min(64,M-m*64)&&cell%128<std::min(128,N-n*128)',
        '(compact?cell<M*N:(cell/128<std::min(64,M-m*64)&&cell%128<std::min(128,N-n*128)))')
    revised=once(revised,'inline void write(void* p,int m,int n){if(active)active->write(p,m,n);}',
        'inline void write(void* p,int m,int n,int pitch){if(active)active->write(p,m,n,pitch);}')
    shim=(BUILD/'cpu_shim.hpp').read_text(encoding='utf-8');shim=once(shim,audit,revised)
    shim=once(shim,'namespace OpStats {','namespace OpStats {\ninline std::atomic<uint64_t> addElements{0};')
    shim=once(shim,'inline void reset(){duplicateElements=0;','inline void reset(){addElements=0;duplicateElements=0;')
    shim=once(shim,'LocalTensor<T>b,int n){for(int i=0;i<n;++i)d.SetValue(i,a.GetValue(i)+b.GetValue(i));}',
        'LocalTensor<T>b,int n){OpStats::addElements+=n;for(int i=0;i<n;++i)d.SetValue(i,a.GetValue(i)+b.GetValue(i));}')
    b.write(BUILD/'cpu_shim.hpp',shim)
    model=(BUILD/'cube_model.hpp').read_text(encoding='utf-8')
    b.write(BUILD/'cube_model.hpp',once(model,'SplitAudit::write(d.p,p.mSize,p.nSize);','SplitAudit::write(d.p,p.mSize,p.nSize,p.dstStride);'))

def harness(compact):
    s='#define SPLIT_VARIANT 2\n#define COMPACT_VARIANT '+str(int(compact))+'\n'+(ROOT/'V11_split_k/source_checks.cpp.in').read_text(encoding='utf-8')
    s=once(s,'#define BMMS23_CPU_TEST 1','#define BMMS23_CPU_TEST 1\n#define BMMS28_CPU_TEST 1')
    s=once(s,'#include "split_extracted.hpp"','#include "split_extracted.hpp"\n#include "compact_extracted.hpp"')
    s=once(s,'    auto old=bmms11d::MakePlan',
        '    bool compact=COMPACT_VARIANT&&bmms28::Eligible(B,M,N,K,std::is_same_v<T,half>?1:2,cores);\n    auto old=bmms11d::MakePlan')
    s=once(s,'selected?p.splits:1,blocks);','selected?p.splits:1,blocks,compact);')
    s=once(s,'                if(selected){bmms23::Producer',
        '                if(compact){bmms28::Producer<T,TA,TB> op;op.Init((GM_ADDR)a.data(),(GM_ADDR)b.data(),(GM_ADDR)ws.data(),p,&pipe);op.Process();}\n                else if(selected){bmms23::Producer')
    s=once(s,'                if(selected){bmms23::Consumer',
        '                if(compact){bmms28::Consumer op;op.Init((GM_ADDR)ws.data(),(GM_ADDR)y.data(),p,&pipe);op.Process();}\n                else if(selected){bmms23::Consumer')
    pos='        std::vector<uint32_t> bits;'
    s=once(s,pos,'''        int stripe=compact?std::min(M,(32768/S/N/16)*16):16;
        uint64_t copies=compact?(M+stripe-1)/stripe:S*(M/16);
        Mock::need(splitAudit.dmaCalls==copies,"unexpected epilogue DMA count");
#ifndef NEGATIVE_MAX_K
        Mock::need(OpStats::addElements==uint64_t(S-1)*M*(compact?N:128),"unexpected K tree vector work");
#endif
        std::ostringstream work;
        work<<"{\\"splits\\":"<<S<<",\\"stripes\\":"<<((M+stripe-1)/stripe)
            <<",\\"dma_calls\\":"<<splitAudit.dmaCalls<<",\\"K_add_elements\\":"<<OpStats::addElements.load()
            <<",\\"GM_C_bytes\\":"<<Traffic::cWriteBytes.load()<<",\\"barriers\\":"<<ctx.barrier.generation<<"}";
        if(fixtures.count(key))Mock::need(fixtures[key]==work.str(),"work changed on repeat");fixtures[key]=work.str();
'''+pos)
    start=s.index('    for(int rev=0;rev<2;++rev){',s.index('int main()'))
    end=s.index('    std::cout<<std::setprecision',start)
    s=s[:start]+'''#ifdef NEGATIVE_PITCH
    run<half,false,false>(1,16,16,4096,20,0,false);return 7;
#endif
#ifdef NEGATIVE_STRIDE
    run<half,false,false>(1,48,80,8192,20,0,false);return 7;
#endif
    for(int rev=0;rev<2;++rev){
        for(int K:{4096,4128,8192}){layouts<half>(1,16,16,K,20,0,rev);layouts<bfloat16_t>(1,16,16,K,20,0,rev);}
        for(auto d:std::vector<std::array<int,3>>{{32,64,4096},{48,80,8192},{64,64,8192},{16,128,4096}}){
            auto[M,N,K]=d;run<half,false,false>(1,M,N,K,20,0,rev);run<bfloat16_t,true,true>(1,M,N,K,20,0,rev);
        }
        for(int pat:{1,2,3}){
            run<half,false,true>(1,32,48,4160,20,pat,rev);
            run<bfloat16_t,true,false>(1,48,96,4096,20,pat,rev);
        }
    }
''' + s[end:]
    # 48x96 is a deliberate non-target boundary (MN>4096), retaining R25.
    s=once(s,'std::cout<<"},\\"cann_compiled\\":false,\\"npu_tested\\":false}\\n";',
        'std::cout<<"},\\"peak_UB_bytes\\":"<<OpStats::peak[0].load()<<",\\"cann_compiled\\":false,\\"npu_tested\\":false}\\n";')
    return s

def call(args,stem,error=None):
    p=subprocess.run(args,cwd=BUILD,capture_output=True,text=True,timeout=900)
    b.write(BUILD/(stem+'.stdout.txt'),p.stdout);b.write(BUILD/(stem+'.stderr.txt'),p.stderr)
    if error:assert p.returncode and error in p.stderr,(stem,p.returncode,p.stderr)
    elif p.returncode:raise RuntimeError(stem+': '+p.stderr[-4000:])
    return p

def main():
    b.verify();BUILD.mkdir(exist_ok=True);prepare()
    compiler=shutil.which('g++');assert compiler
    args=[compiler,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-pthread','-DCHECK_R01=1','source_checks.cpp']
    runs={}
    for version in ['R25','R28']:
        source=harness(version=='R28');b.write(BUILD/'source_checks.cpp',source);exe=BUILD/(version+'.exe')
        stamp=dict(source_sha256=b.sha(b.BASE if version=='R25' else b.OUT/(b.NAME+'.asc')),
            harness_sha256=b.hashlib.sha256(source.encode()).hexdigest(),headers={p.name:b.sha(p) for p in BUILD.glob('*.hpp')})
        sp=HERE/(version+'_INPUTS.json');rp=HERE/(version+'_CPU_RESULT.json')
        if '--resume' in sys.argv and sp.exists() and json.loads(sp.read_text())==stamp:
            result=json.loads(rp.read_text())
        else:
            call(args+['-o',str(exe)],version+'_compile');result=json.loads(call([str(exe)],version+'_run').stdout)
        assert result['strict_misses']==0
        b.write(sp,json.dumps(stamp,indent=2)+'\n');b.write(rp,json.dumps(result,indent=2)+'\n');runs[version]=result
        print(version+': '+json.dumps({k:v for k,v in result.items() if k not in ['output_bits','fixtures']}),flush=True)
    assert runs['R25']['output_bits']==runs['R28']['output_bits']
    negatives={};header=BUILD/'compact_extracted.hpp';good=header.read_text(encoding='utf-8')
    for name,a,z,define,error in [
        ('PITCH','f.dstStride=p.N;','f.dstStride=TN;','NEGATIVE_PITCH','split write pitch mismatch'),
        ('STRIDE','(TM*TN-cells)*4','(TM*TN-p.M*p.N)*4','NEGATIVE_STRIDE','split DMA reads GM padding'),
        ('K_TREE','AscendC::Add(values,values,values[count],count);','AscendC::Max(values,values,values[count],count);','NEGATIVE_MAX_K','max before full K sum corrupts output'),
        ('PUBLICATION','        AscendC::SyncAll<true>();','        // missing barrier','NEGATIVE_PUBLICATION','split partial read before publication barrier')]:
        b.write(BUILD/'source_checks.cpp',harness(True));b.write(header,once(good,a,z))
        try:
            exe=BUILD/(name+'.exe');call(args+['-D'+define+'=1','-o',str(exe)],name+'_compile')
            p=call([str(exe)],name+'_run',error)
        finally:b.write(header,good)
        negatives[name]=dict(rejected=True,message=p.stderr.strip());print(name+': rejected',flush=True)
    inherited=json.loads((ROOT/'V11_split_k/CHECKS.json').read_text())['artifacts']
    for rel,digest in inherited.items():assert b.sha(ROOT/rel)==digest,rel
    artifacts=dict(inherited)
    for p in [HERE/'build.py',Path(__file__),HERE/'consumer.asc',HERE/'compact_fragment.asc',ROOT/'V11_split_k/run_checks.py']:
        artifacts[p.relative_to(ROOT).as_posix()]=b.sha(p)
    report=dict(scope='actual-source CPU Cube/Vector model, ordinary finite inputs; not CANN or NPU validation',
        output_bits_equal_R25=True,negative_controls=negatives,composition=b.verify(),
        runs={v:{k:x for k,x in r.items() if k not in ['output_bits','fixtures']} for v,r in runs.items()},
        representative_work={v:{k:x for k,x in r['fixtures'].items() if k in ['f1600_1_32_64_4096_20_0','f1600_1_48_80_8192_20_0','f1600_1_64_64_8192_20_0']} for v,r in runs.items()},
        sources={p.name:b.sha(p) for p in b.OUT.glob('*.asc')},artifacts=artifacts,
        CANN_compiled_locally=False,NPU_tested_locally=False,full_domain_precision_proven=False)
    for p in [HERE/'CHECKS.json',b.OUT/'CPU_CHECKS.json']:b.write(p,json.dumps(report,indent=2)+'\n')
    print('Actual source, bitwise comparison, ownership and fault controls passed.',flush=True)
if __name__=='__main__':main()

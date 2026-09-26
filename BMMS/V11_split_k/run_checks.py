"""Execute real Cube/Vector source, K1 ablation, baseline and controlled faults."""
from pathlib import Path
import importlib.util,json,shutil,subprocess,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;BUILD=HERE/'cpu_build'
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
build=load('split_builder',HERE/'build.py');native=load('native_checks',ROOT/'V11_native_specialize/run_checks.py')
native.BUILD=BUILD;native.previous.BUILD=BUILD;native.previous.flex.BUILD=BUILD;native.previous.flex.redirect(native.previous.flex.prior)
once=build.once
def call(args,stem,error=None):
    p=subprocess.run(args,cwd=BUILD,capture_output=True,text=True,timeout=900)
    build.write(BUILD/(stem+'.stdout.txt'),p.stdout);build.write(BUILD/(stem+'.stderr.txt'),p.stderr)
    if error:assert p.returncode and error in p.stderr,(stem,p.stderr)
    elif p.returncode:raise RuntimeError(f'{stem}: {p.returncode}: {p.stderr[-3000:]} {p.stdout[-1000:]}')
    return p
def prepare():
    native.prepare('R14');fragment=(HERE/'split_k_fragment.asc').read_text(encoding='utf-8')
    assert fragment in (build.OUT/(build.NAMES['R23']+'.asc')).read_text(encoding='utf-8')
    extract=native.previous.flex.prior.prior.prior.prior.parent.previous.parent.extract
    build.write(BUILD/'split_extracted.hpp',extract(fragment,'// BMMS23_CPU_EXTRACT_END'))
    shim=(BUILD/'cpu_shim.hpp').read_text(encoding='utf-8')
    shim=once(shim,'namespace RingAudit {',(HERE/'publication_audit.hpp').read_text(encoding='utf-8')+'\nnamespace RingAudit {')
    shim=once(shim,'    RingAudit::read(s.p,uint64_t(cp.blockCount)*cp.blockLen/sizeof(T));',
        '    SplitAudit::read(s.p,cp.blockCount,cp.blockLen,cp.srcStride);\n    RingAudit::read(s.p,uint64_t(cp.blockCount)*cp.blockLen/sizeof(T));')
    shim=once(shim,'if constexpr(MODE==2)RingAudit::signal(id);','if constexpr(MODE==2){if(Mock::cube)SplitAudit::ready(id);RingAudit::signal(id);}')
    old='Mock::flags->wait<MODE>((MODE==2 && id>=4 && id<=7)?id-4:id);'
    shim=once(shim,old,old+'if constexpr(MODE==2){if(!Mock::cube)SplitAudit::wait(id);}')
    shim=once(shim,'need(published==released&&released==acquired&&consumed==published*2,"token conservation failure");',
        'if(SplitAudit::active)need(published==pairs.size()&&released==0&&acquired==0&&consumed==published*2,"immutable publication token conservation failure");'
        'else need(published==released&&released==acquired&&consumed==published*2,"token conservation failure");')
    build.write(BUILD/'cpu_shim.hpp',shim)
    model=(BUILD/'cube_model.hpp').read_text(encoding='utf-8')
    model=once(model,'    RingAudit::write(d.p,uint64_t(p.mSize)*p.nSize);','    SplitAudit::write(d.p,p.mSize,p.nSize);\n    RingAudit::write(d.p,uint64_t(p.mSize)*p.nSize);')
    # Decode and validate each L0 input element once, before arithmetic. The old
    # model redundantly checked the same immutable element for every dot product.
    begin=model.index('    for(int m=0;m<p.m;++m)for(int n=0;n<p.n;++n){',model.index('template<class T>void Mmad('))
    end=model.index('\n}\n',begin)
    model=model[:begin]+'''    std::vector<float> av(p.m*p.k),bv(p.k*p.n);
    for(int m=0;m<p.m;++m)for(int k=0;k<p.k;++k)
        av[m*p.k+k]=float(a.GetValue(((m/16)*(p.k/16)+k/16)*256+(m%16)*16+k%16));
    for(int k=0;k<p.k;++k)for(int n=0;n<p.n;++n)
        bv[k*p.n+n]=float(b.GetValue(((k/16)*(p.n/16)+n/16)*256+(n%16)*16+k%16));
    for(int m=0;m<p.m;++m)for(int n=0;n<p.n;++n){
        int ci=(n/16)*p.m*16+m*16+n%16;float v=p.cmatrixInitVal?0:c.GetValue(ci);
        for(int k=0;k<p.k;++k)v=std::fma(av[m*p.k+k],bv[k*p.n+n],v);
        c.SetValue(ci,v);
    }'''+model[end:]
    build.write(BUILD/'cube_model.hpp',model)
def harness(version):return f'#define SPLIT_VARIANT {0 if version=="R14" else 1 if version=="K1" else 2}\n'+(HERE/'source_checks.cpp.in').read_text(encoding='utf-8')
def main():
    build.verify();BUILD.mkdir(exist_ok=True);compiler=shutil.which('g++');assert compiler
    args=[compiler,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-pthread','-DCHECK_R01=1','source_checks.cpp']
    runs={}
    for version in ['R14','K1','R23']:
        prepare();source=harness(version);build.write(BUILD/'source_checks.cpp',source);exe=BUILD/(version+'.exe')
        stamp={'production_sha256':build.sha(build.BASE if version=='R14' else build.OUT/(build.NAMES[version]+'.asc')),
               'harness_sha256':build.hashlib.sha256(source.encode()).hexdigest(),'headers':{p.name:build.sha(p) for p in BUILD.glob('*.hpp')}}
        stamp_path=HERE/(version+'_INPUTS.json')
        if '--resume' in sys.argv and stamp_path.exists() and json.loads(stamp_path.read_text(encoding='utf-8'))==stamp:
            data=json.loads((HERE/(version+'_CPU_RESULT.json')).read_text(encoding='utf-8'))
        else:
            call(args+['-o',str(exe)],version+'_compile');data=json.loads(call([str(exe)],version+'_run').stdout)
        assert data['strict_misses']==0
        build.write(stamp_path,json.dumps(stamp,indent=2)+'\n');runs[version]=data
        build.write(HERE/(version+'_CPU_RESULT.json'),json.dumps(data,indent=2)+'\n')
        print(version+': '+json.dumps({k:v for k,v in data.items() if k!='output_bits'}),flush=True)
    assert runs['R14']['output_bits']==runs['K1']['output_bits']
    for key,baseline in runs['R14']['output_bits'].items():
        if not key.endswith('_3'):assert runs['R23']['output_bits'][key]==baseline,key
    negatives={}
    for name,a,b,define,error in [
        ('K_ORIGIN','kBegin=(ks*units/p.splits)*32,kEnd=((ks+1)*units/p.splits)*32',
         'kBegin=0,kEnd=(((ks+1)*units/p.splits)-(ks*units/p.splits))*32','NEGATIVE_K_ORIGIN','wrong K origin corrupts output'),
        ('MAX_K','AscendC::Add(values,values,values[count],count);','AscendC::Max(values,values,values[count],count);','NEGATIVE_MAX_K','max before full K sum corrupts output'),
        ('PUBLICATION','        AscendC::SyncAll<true>();','        // missing publication barrier','NEGATIVE_PUBLICATION','split partial read before publication barrier')]:
        prepare();build.write(BUILD/'source_checks.cpp',harness('R23'));p=BUILD/'split_extracted.hpp';good=p.read_text(encoding='utf-8');build.write(p,once(good,a,b))
        try:
            exe=BUILD/(name+'.exe');call(args+['-D'+define+'=1','-o',str(exe)],name+'_compile');bad=call([str(exe)],name+'_run',error)
        finally:build.write(p,good)
        negatives[name]={'rejected':True,'stderr':bad.stderr.strip()};print(name+': rejected',flush=True)
    inherited=json.loads((ROOT/'V11_native_specialize/CHECKS.json').read_text(encoding='utf-8'))['artifacts']
    for rel,digest in inherited.items():assert build.sha(ROOT/rel)==digest,rel
    artifacts=dict(inherited)
    for p in [HERE/'build.py',Path(__file__),HERE/'host_plan.asc',HERE/'consumer.asc',HERE/'split_k_fragment.asc',HERE/'source_checks.cpp.in',HERE/'publication_audit.hpp',ROOT/'V11_native_specialize/run_checks.py']:
        artifacts[p.relative_to(ROOT).as_posix()]=build.sha(p)
    report={'scope':'actual-source CPU memory/layout/publication/arithmetic model; no CANN/NPU validation',
            'sources':{p.name:build.sha(p) for p in build.OUT.glob('*.asc')},'composition':build.verify(),
            'K1_outputs_equal_R14_bitwise':True,'dyadic_outputs_equal_R14_bitwise':True,
            'general_inputs_checked_against_FP64_reference':True,'negative_controls':negatives,
            'runs':{v:{k:x for k,x in r.items() if k!='output_bits'} for v,r in runs.items()},
            'artifacts':artifacts,'cann_compiled_locally':False,'npu_tested_locally':False,'full_domain_precision_proven':False}
    for p in [HERE/'CHECKS.json',build.OUT/'CPU_CHECKS.json']:build.write(p,json.dumps(report,indent=2)+'\n')
    print('Split-K source and negative controls passed.',flush=True)
if __name__=='__main__':main()

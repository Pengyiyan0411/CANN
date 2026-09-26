"""Check actual R04/R05/R06 source, packing, padding, ring ownership and API counts."""
from pathlib import Path
import importlib.util
import json
import os
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BUILD = HERE / 'cpu_build'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


build = load('lowlevel_build', HERE / 'build.py')
parent = load('r04_checks', ROOT / 'V11_merge/run_checks.py')
parent.BUILD = parent.previous.BUILD = parent.previous.parent.BUILD = BUILD
once = build.once


def call(argv, label, failure=None):
    result = subprocess.run(argv, cwd=BUILD, capture_output=True, text=True, timeout=300)
    build.write(BUILD / (label + '.stdout.txt'), result.stdout)
    build.write(BUILD / (label + '.stderr.txt'), result.stderr)
    if failure is None:
        if result.returncode:
            raise RuntimeError(f'{label}: {result.returncode}: {result.stderr[-4000:]}')
    else:
        assert result.returncode != 0 and failure in result.stderr, (label, result.returncode, result.stderr)
    return result


def prepare(version):
    parent.prepare()
    source = (build.BASE if version == 'R04' else build.OUT / (build.NAMES[version] + '.asc')).read_text(encoding='utf-8')
    macro = (ROOT / 'V11_followup/macro_ring_fragment.asc').read_text(encoding='utf-8')
    if version == 'R05':
        macro = once(macro, build.consumer(macro, True), build.consumer(source, True))
    if version == 'R06':
        macro = (HERE / 'r06_macro_fragment.asc').read_text(encoding='utf-8')
    assert source.count(macro) == 1
    extract = parent.previous.parent.extract
    build.write(BUILD / 'ring_extracted.hpp', extract(macro, '// BMMS11R2_CPU_EXTRACT_END'))
    common = (BUILD / 'common_extracted.hpp').read_text(encoding='utf-8')
    old_consumer = build.consumer(build.BASE.read_text(encoding='utf-8'))
    producer = build.between(source, 'template<class T,bool TA,bool TB,int TK>\nclass SmallKProducer {', 'class SmallKConsumer {')
    # Native small-K shares the consumer modified by R05, so execute it too.
    common = once(common, old_consumer, producer + build.consumer(source))
    build.write(BUILD / 'common_extracted.hpp', common)
    shim = (BUILD / 'cpu_shim.hpp').read_text(encoding='utf-8')
    stats = '''namespace OpStats {
inline std::atomic<uint64_t> duplicateElements{0},reduceCalls{0},reduceRows{0},manualVToMte2{0};
inline std::array<std::atomic<uint64_t>,5> peak{};
inline void charge(int arena,uint64_t n){auto old=peak[arena].load();while(old<n&&!peak[arena].compare_exchange_weak(old,n)){};}
inline void reset(){duplicateElements=0;reduceCalls=0;reduceRows=0;manualVToMte2=0;}
}
'''
    shim = shim.replace('namespace AscendC {', stats + '\nnamespace AscendC {', 1)
    shim = once(shim, 'used[arena]+=n;Mock::need', 'used[arena]+=n;OpStats::charge(arena,used[arena]);Mock::need')
    shim = once(shim, 'allocated=true;return {storage,0};',
                'allocated=true;std::fill(storage->init.begin(),storage->init.end(),0);return {storage,0};')
    shim = once(shim, 'template<class T>void Duplicate(LocalTensor<T> d,T x,int n){',
                'template<class T>void Duplicate(LocalTensor<T> d,T x,int n){OpStats::duplicateElements+=n;')
    shim = once(shim, 'inline void WholeReduceMax(LocalTensor<float>d,LocalTensor<float>s,int mask,int repeats,int ds,int bs,int rs,ReduceOrder){',
                'inline void WholeReduceMax(LocalTensor<float>d,LocalTensor<float>s,int mask,int repeats,int ds,int bs,int rs,ReduceOrder){++OpStats::reduceCalls;OpStats::reduceRows+=repeats;')
    shim = once(shim, 'template<HardEvent E>void SetFlag(int id){',
                'template<HardEvent E>void SetFlag(int id){if constexpr(E==HardEvent::V_MTE2)++OpStats::manualVToMte2;')
    # A completed M_FIX wait drains M before the next operation. This matters for
    # the unchanged native producer, which computes one tile and waits M_FIX.
    shim = once(shim, 'template<HardEvent E>void WaitFlag(int id){',
                'template<HardEvent E>void WaitFlag(int id){if constexpr(E==HardEvent::M_FIX)Mock::smallMmadPending=false;')
    build.write(BUILD / 'cpu_shim.hpp', shim)
    model = (BUILD / 'cube_model.hpp').read_text(encoding='utf-8')
    model = once(model, 'Mock::need(p.repeatTimes>0&&p.repeatTimes<=255&&p.srcStride>0,"invalid LoadData model params");',
                 '''Mock::need(p.repeatTimes>0&&p.repeatTimes<=255&&p.srcStride>0&&p.srcStride<=65535&&
        p.dstGap>=0&&p.dstGap<=65535,"invalid LoadData model params");
    Mock::need(d.offset%512==0&&s.offset%32==0,"LoadData address alignment");''')
    model = once(model, 'Mock::need(p.m%16==0&&p.n%16==0&&p.k%16==0,"unaligned Mmad model dimensions");',
                 '''Mock::need(p.m%16==0&&p.n%16==0&&p.k%16==0,"unaligned Mmad model dimensions");
    Mock::need(c.offset%1024==0&&a.offset%512==0&&b.offset%512==0,"Mmad address alignment");''')
    build.write(BUILD / 'cube_model.hpp', model)


def harness():
    source = parent.harness()
    source = once(source, 'int macroRoutes=0,residualRoutes=0,guardChecks=0;',
                  'int macroRoutes=0,residualRoutes=0,smallRoutes=0,guardChecks=0;')
    source = once(source, '    bool useMacro=bmms11r2::Eligible(B,M,N,K,cores);', '''    bool useMacro=bmms11r2::Eligible(B,M,N,K,cores);
    bool useSmall=bmms83::NativeEligible(M,N,K)&&!bmms71::UseResident(M,N,K);''')
    source = once(source, 'Mock::need(useMacro||bmms11d::ResidualEligible(B,M,N,K,cores),"CPU fixture outside R04 dense domain");',
                  'Mock::need(useMacro||useSmall||bmms11d::ResidualEligible(B,M,N,K,cores),"CPU fixture outside tested production domains");')
    source = once(source, 'auto p=useMacro?bmms11r2::MakePlan(B,M,N,K,cores):bmms11d::MakePlan(B,M,N,K,cores);',
                  'auto p=useMacro?bmms11r2::MakePlan(B,M,N,K,cores):useSmall?bmms83::MakeNative(B,M,N,K,cores):bmms11d::MakePlan(B,M,N,K,cores);')
    source = once(source, 'if(useMacro)++macroRoutes;else ++residualRoutes;',
                  'if(useMacro)++macroRoutes;else if(useSmall)++smallRoutes;else ++residualRoutes;\n    OpStats::reset();')
    source = once(source, 'const auto ringBytes=useMacro?bmms11r2::RingBytes(p):bmms11d::RingBytes(p);',
                  'const auto ringBytes=useMacro?bmms11r2::RingBytes(p):useSmall?bmms83::NativeRingBytes(p):bmms11d::RingBytes(p);')
    source = once(source, 'const auto partialBytes=useMacro?bmms11r2::PartialBytes(p):bmms11d::PartialBytes(p);',
                  'const auto partialBytes=useMacro?bmms11r2::PartialBytes(p):useSmall?bmms83::NativePartialBytes(p):bmms11d::PartialBytes(p);')
    source = once(source, 'else{bmms11d::StagedProducer<T,TA,TB> op;runProducer(op);}', '''else if(useSmall){
                    if(K==32){bmms83::SmallKProducer<T,TA,TB,32> op;runProducer(op);}
                    else if(K==64){bmms83::SmallKProducer<T,TA,TB,64> op;runProducer(op);}
                    else{bmms83::SmallKProducer<T,TA,TB,128> op;runProducer(op);}
                }else{bmms11d::StagedProducer<T,TA,TB> op;runProducer(op);}''')
    source = once(source, 'int main(){try{', (HERE / 'metrics.cpp.in').read_text(encoding='utf-8') + '\nint main(){try{')
    source = once(source, '    guards();', '''#ifdef NEGATIVE_PADDING
    dense<half,false,false>(1,16,16,352,1,0,false);return 7;
#endif
#ifdef NEGATIVE_PACKING
    dense<half,false,false>(1,128,256,256,1,0,false);
    if(strictMisses)throw std::runtime_error("incorrect output after broken L0C stride");
    return 7;
#endif
    guards();''')
    # Add small-K coverage because R05 also changes bmms83::SmallKConsumer.
    source = once(source, '    std::ostringstream mixedRoutes,mixedRings,mixedReady;', '''    for(int rev=0;rev<2;++rev){
        for(auto d:std::vector<std::array<int,5>>{
            {1,16,32,32,1},{1,80,144,64,2},{3,144,272,128,4},{1,272,1040,32,1}}){
            layouts<half>(d,0,rev);layouts<bfloat16_t>(d,0,rev);
        }
        for(int pat:{1,2}){
            dense<half,false,true>(1,144,528,64,2,pat,rev);
            dense<bfloat16_t,true,false>(1,144,528,64,2,pat,rev);
        }
        dense<half,false,false>(1,8192,16,32,2,0,rev);
        dense<bfloat16_t,true,true>(1,8192,16,32,2,0,rev);
        // Simultaneous M/N/K tails exercise the packed macro layout.
        dense<half,true,true>(1,144,272,288,1,0,rev);
        dense<bfloat16_t,false,false>(1,144,272,288,1,1,rev);
    }
    std::ostringstream fixtures;
    Traffic::reset();dense<half,false,false>(1,128,1024,256,1,0,false);
    fixtures<<"\\\"macro_wide\\\":"<<metrics();
    Traffic::reset();dense<half,false,false>(1,64,2048,256,1,0,false);
    fixtures<<",\\\"residual_wide\\\":"<<metrics();
    Traffic::reset();dense<half,false,false>(1,256,2048,32,1,0,false);
    fixtures<<",\\\"native_wide\\\":"<<metrics();
    std::ostringstream mixedRoutes,mixedRings,mixedReady;''')
    source = once(source, '<<",\\\"guard_checks\\\":"<<guardChecks',
                  '<<",\\\"guard_checks\\\":"<<guardChecks<<",\\\"small_k_route_runs\\\":"<<smallRoutes'
                  '<<",\\\"fixtures\\\":{"<<fixtures.str()<<"}"'
                  '<<",\\\"peak_arena_bytes\\\":["<<OpStats::peak[0]<<","<<OpStats::peak[1]<<","<<OpStats::peak[2]<<","<<OpStats::peak[3]<<","<<OpStats::peak[4]<<"]"')
    return source


def compile_run(version, compiler):
    prepare(version)
    build.write(BUILD / 'source_checks.cpp', harness())
    args = [compiler, '-std=c++20', '-O2', '-fno-fast-math', '-ffp-contract=off', '-pthread',
            '-DCHECK_R01=1', '-DCHECK_R04=1', 'source_checks.cpp']
    exe = BUILD / (version + ('.exe' if os.name == 'nt' else ''))
    call(args + ['-o', str(exe)], version + '_compile')
    data = json.loads(call([str(exe)], version + '_run').stdout)
    build.write(HERE / (version + '_CPU_RESULT.json'), json.dumps(data, indent=2) + '\n')
    print(version + ': ' + json.dumps({k:v for k,v in data.items() if k != 'output_bits'}), flush=True)
    return data, args


def main():
    build.verify()
    compiler = shutil.which(os.environ.get('CXX', 'g++'))
    if not compiler:
        raise RuntimeError('g++ required')
    runs = {}
    for version in ['R04', 'R05', 'R06']:
        runs[version], args = compile_run(version, compiler)
        assert runs[version]['source_runs'] == 256 and runs[version]['repeat_pairs'] == 128
        assert (runs[version]['macro_route_runs'], runs[version]['residual_route_runs'], runs[version]['small_k_route_runs']) == (103, 79, 77)
        assert runs[version]['strict_misses'] == runs[version]['combined_misses'] == 0
        assert runs[version]['known_precision_limitations'] == 3
    assert runs['R04']['output_bits'] == runs['R05']['output_bits'] == runs['R06']['output_bits']
    prior = json.loads((ROOT / 'V11_merge/R04_CPU_RESULT.json').read_text(encoding='utf-8'))
    for key, bits in prior['output_bits'].items():
        assert runs['R04']['output_bits'][key] == bits
    full = {v:r['traffic_fixture'] for v,r in runs.items()}
    assert full['R04']['mmads'] == 16 and full['R06']['mmads'] == 4
    assert full['R04']['l0_calls'] == 64 and full['R06']['l0_calls'] == 32
    for key in full['R04']:
        if key not in ['mmads', 'l0_calls']:
            assert full['R04'][key] == full['R06'][key], key
    for fixture in ['macro_wide', 'residual_wide', 'native_wide']:
        old, new = runs['R04']['fixtures'][fixture], runs['R05']['fixtures'][fixture]
        assert old['reduce_calls'] == 4 * new['reduce_calls']
        # One final ReduceSum-workspace reuse fence remains in both versions.
        assert new['manual_v_mte2'] == 1 and old['manual_v_mte2'] == 2 * old['fixpipes'] + 1
        assert new['duplicate_elements'] < old['duplicate_elements']
        for key in ['gm_bytes','l0_bytes','mmads','fixpipes','c_write_bytes','ready','free']:
            assert old[key] == new[key], (fixture, key)
    failures = {}
    for version, header, old, new, define, message in [
        ('R05', 'common_extracted.hpp', 'if(nr<TN){', 'if(false){', 'NEGATIVE_PADDING', 'UB uninitialized read'),
        ('R06', 'ring_extracted.hpp', 'f.srcStride=ar;', 'f.srcStride=mr;', 'NEGATIVE_PACKING', 'incorrect output')]:
        prepare(version)
        path = BUILD / header
        good = path.read_text(encoding='utf-8')
        build.write(path, once(good, old, new))
        exe = BUILD / (define + ('.exe' if os.name == 'nt' else ''))
        try:
            call(args + ['-D' + define + '=1', '-o', str(exe)], define + '_compile')
            result = call([str(exe)], define + '_run', failure=message)
        finally:
            build.write(path, good)
        failures[define] = {'rejected': True, 'returncode': result.returncode, 'stderr': result.stderr.strip()}
    artifacts = {}
    previous = json.loads((ROOT / 'V11_merge/CHECKS.json').read_text(encoding='utf-8'))
    for rel, digest in previous['artifacts'].items():
        assert build.sha(ROOT / rel) == digest, rel
        artifacts[rel] = digest
    for path in [Path(__file__), HERE / 'build.py', HERE / 'metrics.cpp.in', HERE / 'r05_macro_consumer.asc',
                 HERE / 'r05_micro_consumer.asc', HERE / 'r06_macro_fragment.asc', ROOT / 'V11_merge/run_checks.py',
                 ROOT / 'V11_merge/R04_CPU_RESULT.json']:
        artifacts[path.relative_to(ROOT).as_posix()] = build.sha(path)
    report = {'scope': 'actual-source CPU model and logical API counts; not CANN compilation, hardware simulation or timing',
              'sources': {p.name:build.sha(p) for p in build.OUT.glob('*.asc')}, 'composition': build.verify(),
              'ordinary_outputs_equal_bitwise': True, 'known_numerical_limitations_remain': True,
              'negative_controls': failures, 'cann_compiled_locally': False, 'npu_tested_locally': False,
              'model_refinements': ['queue allocation clears initializedness', 'M_FIX wait drains pending M instruction',
                                    'LoadData/Mmad local offset alignment checked', 'vector and arena counters'],
              'runs': {k:{kk:vv for kk,vv in v.items() if kk!='output_bits'} for k,v in runs.items()},
              'artifacts': artifacts}
    for path in [HERE / 'CHECKS.json', build.OUT / 'CPU_CHECKS.json']:
        build.write(path, json.dumps(report, indent=2) + '\n')
    print('All three versions match. R05 reduces repeated vector work; R06 MMAD 16->4, LoadData 64->32.', flush=True)


if __name__ == '__main__':
    main()

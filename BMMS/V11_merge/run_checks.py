"""Exercise R04's two source paths with their own workspace and ring protocols."""
from pathlib import Path
import importlib.util
import json
import os
import shutil
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


merge = load('merge_build', HERE / 'build.py')
previous = load('followup_checks', ROOT / 'V11_followup/run_checks.py')
previous.BUILD = previous.parent.BUILD = BUILD
once = merge.once


def prepare():
    merge.verify()
    previous.prepare()
    # Only the domain complement reference changed; extract this actual R04 fragment.
    fragment = (HERE / 'residual_dense_fragment.asc').read_text(encoding='utf-8')
    assert fragment in merge.SOURCE.read_text(encoding='utf-8')
    merge.write(BUILD / 'residual_extracted.hpp', previous.parent.extract(fragment, '// BMMS9_CPU_EXTRACT_END'))


def harness():
    s = previous.harness().replace('CHECK_R03', 'CHECK_R04').replace('useR01', 'useMacro')
    s = s.replace('r01Routes', 'macroRoutes').replace('r01_route_runs', 'macro_route_runs')
    s = once(s, 'bool useMacro=bmms11::Eligible', 'bool useMacro=bmms11r2::Eligible')
    s = once(s, 'useMacro?bmms11::MakePlan', 'useMacro?bmms11r2::MakePlan')
    s = once(s, 'if(useMacro){bmms11::ReuseProducer', 'if(useMacro){bmms11r2::ReuseProducer')
    s = once(s, 'if(useMacro){bmms11::RowMaxConsumer', 'if(useMacro){bmms11r2::RowMaxConsumer')
    s = s.replace('CPU fixture outside R03 dense domain', 'CPU fixture outside R04 dense domain')
    s = once(s, 'int macroRoutes=0,residualRoutes=0,guardChecks=0;',
             'int macroRoutes=0,residualRoutes=0,guardChecks=0;\nbool lastMacro=false;uint64_t lastRingPerGroup=0;')
    s = once(s, '    std::vector<float>ring(TEST_NS::RingBytes(p)/4,NAN),part(TEST_NS::PartialBytes(p)/4,NAN),y(B,NAN);', '''    const auto ringBytes=useMacro?bmms11r2::RingBytes(p):bmms11d::RingBytes(p);
    const auto partialBytes=useMacro?bmms11r2::PartialBytes(p):bmms11d::PartialBytes(p);
    lastMacro=useMacro;lastRingPerGroup=ringBytes/p.blocks;
    Mock::need(lastRingPerGroup==(useMacro?262144:65536),"wrong ring size for selected branch");
    std::vector<float>ring(ringBytes/4,NAN),part(partialBytes/4,NAN),y(B,NAN);''')
    needle = '        auto p=bmms11::MakePlan(B,M,N,K,cores);'
    s = once(s, needle, needle + '''
        auto r2=bmms11r2::MakePlan(B,M,N,K,cores);
        Mock::need(p.mTiles==r2.mTiles&&p.nTiles==r2.nTiles&&p.pM==r2.pM&&p.pN==r2.pN&&
            p.tasks==r2.tasks&&p.blocks==r2.blocks,"merged macro plan differs from R01");''')
    needle = '    Traffic::reset();dense<half,false,false>(1,128,256,256,1,0,false);'
    s = once(s, needle, '''    std::ostringstream mixedRoutes,mixedRings,mixedReady;
    for(int i=0;i<4;++i){
        const int cores=i%2?20:1;
        Traffic::reset();dense<half,true,true>(1,128,256,256,cores,0,i%2);
        Mock::need(lastMacro==(cores==1),"core boundary dispatch changed");
        if(i){mixedRoutes<<",";mixedRings<<",";mixedReady<<",";}
        mixedRoutes<<"\\\""<<(lastMacro?"macro":"residual")<<"\\\"";
        mixedRings<<lastRingPerGroup;mixedReady<<RingAudit::lastReady;
    }
''' + needle)
    needle = '<<",\\\"plan_checks\\\":"<<planChecks'
    s = once(s, needle, needle + '<<",\\\"mixed_route_sequence\\\":["<<mixedRoutes.str()<<"]"'
             '<<",\\\"mixed_ring_bytes_per_group\\\":["<<mixedRings.str()<<"]"'
             '<<",\\\"mixed_ready_packets\\\":["<<mixedReady.str()<<"]"')
    return s


def main():
    prepare()
    merge.write(BUILD / 'source_checks.cpp', harness())
    compiler = shutil.which(os.environ.get('CXX', 'g++'))
    if not compiler:
        raise RuntimeError('g++ required')
    base = [compiler, '-std=c++20', '-O2', '-fno-fast-math', '-ffp-contract=off', '-pthread',
            '-DCHECK_R01=1', '-DCHECK_R04=1']
    exe = BUILD / ('R04.exe' if os.name == 'nt' else 'R04')
    previous.call(base + ['source_checks.cpp', '-o', str(exe)], 'R04_compile')
    run = json.loads(previous.call([str(exe)], 'R04_run').stdout)
    assert run['source_runs'] == 173 and run['repeat_pairs'] == 88
    assert run['plan_checks'] == 4494 and run['guard_checks'] == 7560
    assert run['macro_route_runs'] == 98 and run['residual_route_runs'] == 78
    assert run['strict_misses'] == run['combined_misses'] == 0
    assert run['known_precision_limitations'] == 3
    assert run['mixed_route_sequence'] == ['macro', 'residual', 'macro', 'residual']
    assert run['mixed_ring_bytes_per_group'] == [262144, 65536, 262144, 65536]
    assert run['mixed_ready_packets'] == [1, 4, 1, 4]
    old_checks = json.loads((ROOT / 'V11_followup/CHECKS.json').read_text(encoding='utf-8'))
    for rel, digest in old_checks['artifacts'].items():
        assert merge.sha(ROOT / rel) == digest, rel
    old = json.loads((ROOT / 'V11_followup/R03_CPU_RESULT.json').read_text(encoding='utf-8'))
    for key, bits in old['output_bits'].items():
        assert run['output_bits'][key] == bits, key
    r02 = json.loads((ROOT / 'V11_followup/R02_CPU_RESULT.json').read_text(encoding='utf-8'))
    assert run['traffic_fixture'] == r02['traffic_fixture']
    # Verify the ownership checker still detects an early FREE through R04 dispatch.
    header = BUILD / 'ring_extracted.hpp'
    good = header.read_text(encoding='utf-8')
    bad = once(good, 'if(mo+mr==ar&&no+nr==br)', 'if(mo==0&&no==0)')
    mutant = BUILD / ('negative.exe' if os.name == 'nt' else 'negative')
    try:
        merge.write(header, bad)
        previous.call(base + ['-DNEGATIVE_CONTROL=1', 'source_checks.cpp', '-o', str(mutant)], 'negative_compile')
        failure = previous.call([str(mutant)], 'negative_run', expect_failure=True)
    finally:
        merge.write(header, good)
    artifacts = dict(old_checks['artifacts'])
    for path in [HERE / 'build.py', Path(__file__), HERE / 'residual_dense_fragment.asc',
                 ROOT / 'V11_followup/R03_CPU_RESULT.json', ROOT / 'V11_followup/R02_CPU_RESULT.json']:
        artifacts[path.relative_to(ROOT).as_posix()] = merge.sha(path)
    result = {'scope': 'source CPU layout/event/ring-ownership model with merged dispatch; not NPU simulation',
              'source_sha256': merge.sha(merge.SOURCE), 'composition': merge.verify(),
              'cann_compiled_locally': False, 'npu_tested_locally': False,
              'all_prior_R03_bounded_output_records_match_bitwise': True,
              'prior_output_records_compared': len(old['output_bits']),
              'known_numerical_limitations_remain': True,
              'negative_control': {'early_free_rejected': True, 'exit_code': failure.returncode,
                                   'stderr': failure.stderr.strip()},
              'run': {k: v for k, v in run.items() if k != 'output_bits'}, 'artifacts': artifacts}
    merge.write(HERE / 'R04_CPU_RESULT.json', json.dumps(run, indent=2) + '\n')
    for path in [HERE / 'CHECKS.json', merge.OUT / 'CPU_CHECKS.json']:
        merge.write(path, json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'artifacts'}, indent=2), flush=True)


if __name__ == '__main__':
    main()

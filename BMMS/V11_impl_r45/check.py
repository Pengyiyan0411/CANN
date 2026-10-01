"""Compile and exercise actual pack source with an independent padded-bit oracle.

g++ checks the extracted C++ packing function with API stubs, NOT the complete
Ascend source. Pipeline ordering is a bounded CPU DAG model, not NPU simulation.
"""
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
from build import BASE, OUT, NAME, EXPECTED, function_span

HERE = Path(__file__).resolve().parent
BUILD = HERE / 'cpu_build'


def between(s, a, b):
    return s.split(a, 1)[1].split(b, 1)[0]


def main():
    base_raw = BASE.read_bytes()
    new_raw = (OUT/NAME).read_bytes()
    assert hashlib.sha256(base_raw).hexdigest() == EXPECTED
    base = base_raw.decode('utf-8')
    new = new_raw.decode('utf-8')
    stripped = new.split('\r\n', 2)[2]
    bs, be = function_span(base)
    ns, ne = function_span(stripped)
    assert base[:bs] == stripped[:ns] and base[be:] == stripped[ne:]
    sync = r'AscendC::(?:WaitFlag|SetFlag|CrossCoreSetFlag|CrossCoreWaitFlag)<[^\n]+|bmms71::Fence<[^\n]+|pipe->(?:AllocEventID|ReleaseEventID)<[^\n]+'
    assert re.findall(sync, base[bs:be]) == re.findall(sync, stripped[ns:ne])

    # Reuse the actual unchanged planner, and separately compile each actual
    # PackInputs function. The checked function is never rewritten for the test.
    base = base.replace('\r\n', '\n')
    new = new.replace('\r\n', '\n')
    helpers = 'namespace bmms83 {\n' + between(base, 'namespace bmms83 {', 'static inline bool NativeEligible') + '}\n'
    macro = 'namespace bmms11r2 {\n' + between(base, 'namespace bmms11r2 {', 'template<class T,bool TA,bool TB>') + '}\n'
    pieces = []
    for name, text in [('control', base), ('candidate', new)]:
        host = between(text, 'namespace bmms_c8p43 {', '// Both FP16 and BF16')
        s, e = function_span(text)
        pieces.append('namespace '+name+' {\n'+host+text[s:e]+'\n}\n')
    source = (HERE/'pack_model.hpp').read_text(encoding='utf-8') + '\n' + helpers + macro + ''.join(pieces)
    source += (HERE/'check_driver.cpp').read_text(encoding='utf-8')
    BUILD.mkdir(exist_ok=True)
    (BUILD/'pack_check.cpp').write_text(source, encoding='utf-8', newline='\n')
    compiler = shutil.which('g++')
    assert compiler, 'No host C++ compiler'
    result = subprocess.run([compiler,'-std=c++17','-O2','-Wall','-Wextra',str(BUILD/'pack_check.cpp'),'-o',str(BUILD/'pack_check.exe')], capture_output=True,text=True,timeout=60)
    (BUILD/'compile.log').write_text(result.stdout+result.stderr,encoding='utf-8')
    assert result.returncode == 0, result.stderr
    run = subprocess.run([str(BUILD/'pack_check.exe')],capture_output=True,text=True,timeout=180)
    (BUILD/'run.log').write_text(run.stdout+run.stderr,encoding='utf-8')
    assert run.returncode == 0, run.stderr
    report = json.loads(run.stdout)
    report.update({
        'scope': 'Actual extracted PackInputs CPU execution and full-domain packing geometry, not CANN or NPU',
        'candidate_sha256': hashlib.sha256(new_raw).hexdigest(),
        'baseline_sha256': EXPECTED,
        'outside_PackInputs_byte_identical_except_identification_comments': True,
        'all_original_sync_calls_and_order_retained': True,
        'guard_planner_producer_consumer_dispatch_unchanged': True,
        'all_65536_raw_16bit_patterns_covered_per_operand': True,
        'FP16_BF16_numerical_compute_performed': False,
        'four_TA_TB_layouts': True,
        'dirty_UB_and_GM_checked_against_independent_2D_padding_oracle': True,
        'worker_order_and_three_pipe_DAG_reordered': True,
        'cross_worker_barrier_timing_emulated': False,
        'CANN_compiled': False,'NPU_tested': False,'candidate_timing_us': None,
    })
    (OUT/'CPU_CHECKS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()

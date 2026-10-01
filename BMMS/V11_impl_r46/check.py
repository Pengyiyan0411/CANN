"""Compile the actual new planner/consumer with an independent CPU API model.

This is neither the CANN compiler nor a model of Cube precision/pipes/performance.
"""
from pathlib import Path
import json
import shutil
import subprocess
from build import BASE, OUT, NAME, EXPECTED, sha, strip_additions, function

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BUILD = HERE/'cpu_build'


def between(s, start, end):
    return s.split(start,1)[1].split(end,1)[0]


def extract(base, new):
    b=base.replace('\r\n','\n')
    n=new.replace('\r\n','\n')
    helpers=between(b, 'namespace bmmmaxsum_v43 {', '// Degenerate logical M=N=1')
    plans=between(b, '// BMMS_HOST_PLAN_BEGIN', '// BMMS_HOST_PLAN_END')
    flat=function(b, 'static inline bool FlatFastStream(')
    r43guard=function(b, 'static inline bool Eligible(int32_t B,int32_t M,int32_t N,int32_t K,')
    # Only select Eligible from R43, not a preceding unrelated namespace.
    r43guard=function(b[b.index('namespace bmms_c8p43 {'):], 'static inline bool Eligible(')
    prefix='namespace bmmmaxsum_v43 {\n'+helpers+plans+flat+'\n}\n'
    prefix+='namespace bmms_c8p43 {\n'+r43guard+'\n}\n'
    added=n.split('// BMMS_C8F46_BEGIN',1)[1]
    model=between(added,'namespace bmms_c8f46 {','template <typename T, bool TA, bool TB>\nclass FastFusedDevice')
    device='template <typename T, bool TA, bool TB>\nclass FastFusedDevice'+between(added,
        'template <typename T, bool TA, bool TB>\nclass FastFusedDevice',
        'template <typename T, bool TA, bool TB>\n__aicore__ inline void FastFusedEntry(')
    tiler=function(added,'static inline bool GetTiling(')
    return prefix+'namespace bmms_c8f46 {\n'+model+device+tiler+'\n}\n'


def main():
    raw=BASE.read_bytes();candidate=(OUT/NAME).read_bytes()
    assert sha(raw)==EXPECTED
    assert strip_additions(candidate.decode('utf-8')).encode('utf-8')==raw
    BUILD.mkdir(exist_ok=True)
    shutil.copyfile(ROOT/'next_stage/cpu_shim.hpp',BUILD/'cpu_shim.hpp')
    shutil.copyfile(HERE/'tiling_stub.hpp',BUILD/'tiling_stub.hpp')
    shutil.copyfile(HERE/'check_driver.cpp',BUILD/'check_driver.cpp')
    extracted=extract(raw.decode('utf-8'),candidate.decode('utf-8'))
    (BUILD/'extracted.hpp').write_text(extracted,encoding='utf-8',newline='\n')
    compiler=shutil.which('g++')
    assert compiler,'Host g++ unavailable'
    cmd=[compiler,'-std=c++20','-O2','-Wall','-Wextra','-pthread',str(BUILD/'check_driver.cpp'),'-o',str(BUILD/'check.exe')]
    compile_run=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
    (BUILD/'compile.log').write_text(compile_run.stdout+compile_run.stderr,encoding='utf-8')
    assert compile_run.returncode==0,compile_run.stderr
    result=subprocess.run([str(BUILD/'check.exe')],capture_output=True,text=True,timeout=240)
    (BUILD/'run.log').write_text(result.stdout+result.stderr,encoding='utf-8')
    assert result.returncode==0,result.stderr
    report=json.loads(result.stdout)
    # Two deliberate source mutations verify that tests detect missing tails
    # and accidental use of logical body N as the physical input stride.
    mutations={
        'last_tail_tile_omitted':extracted.replace('const int32_t cols = nTilesLocal*p.vecN;',
            'const int32_t cols = (nTilesLocal-(ns==p.pN-1?1:0))*p.vecN;'),
        'body_used_as_physical_stride':extracted.replace('mm.SetOrgShape(p.M, realN, p.K, p.K);','mm.SetOrgShape(p.M, p.N, p.K, p.K);'),
    }
    faults={}
    for name,mutant in mutations.items():
        assert mutant!=extracted
        sub=BUILD/name;sub.mkdir(exist_ok=True)
        for f in ['cpu_shim.hpp','tiling_stub.hpp','check_driver.cpp']:shutil.copyfile(BUILD/f,sub/f)
        (sub/'extracted.hpp').write_text(mutant,encoding='utf-8',newline='\n')
        c=subprocess.run([compiler,'-std=c++20','-O2','-pthread','-DFAULT_CHECK',str(sub/'check_driver.cpp'),'-o',str(sub/'check.exe')],capture_output=True,text=True,timeout=60)
        assert c.returncode==0,c.stderr
        r=subprocess.run([str(sub/'check.exe')],capture_output=True,text=True,timeout=30)
        assert r.returncode!=0 and any(x in r.stderr for x in
            ['numerical mismatch','GM read out of view bounds']), (name,r.stdout,r.stderr)
        faults[name]=r.stderr.strip()
    report.update({
        'source_sha256':sha(candidate),'baseline_sha256':EXPECTED,
        'scope':'Extracted actual C++ planner/consumer with CPU vector/Matmul/host-tiler contract adapters',
        'original_R43_recovered_byte_identically':True,
        'dtypes':['FP16','BF16'],'layouts':['NN','NT','TN','TT'],
        'patterns':['random_dyadic','all_negative_C','tail_only_winner','overlap_winner','zero','K_cancellation'],
        'faults_detected':faults,
        'real_CANN_tiler_run':False,'CANN_compiled':False,'NPU_tested':False,
        'Cube_rounding_and_async_pipes_modeled':False,
        'candidate_timing_us':None,
    })
    (OUT/'CPU_CHECKS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))


if __name__=='__main__':main()

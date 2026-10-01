"""Read-only kernel analysis: exact diff, extracted host plans and pack geometry.

This does not compile an Ascend kernel or emulate NPU performance. The supplied
R43 and frozen R25 are never modified. Generated C++ runs host arithmetic only.
"""
from pathlib import Path
import difflib
import hashlib
import json
import math
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = ROOT.parent / 'R43_CASE8_PADDED_MACRO.asc'
BASE = ROOT / 'BMMS_V11_R25/R25_NATIVE_TARGETED.asc'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def between(text, begin, end):
    return text.split(begin, 1)[1].split(end, 1)[0]


def main():
    base = BASE.read_text(encoding='utf-8')
    new = SOURCE.read_text(encoding='utf-8')
    assert sha(BASE) == '7defd06457ddb0e356cbf4cc8407f31cbb7c622acf6efd66070be212fa4eacb2'
    assert sha(SOURCE) == '15e2c9a0f73e7534c26400107389dcd8e5cf685b5f6f477c7a3684ad3991df2d'
    ops = difflib.SequenceMatcher(None, base.splitlines(keepends=True), new.splitlines(keepends=True), autojunk=False).get_opcodes()
    changes = [x for x in ops if x[0] != 'equal']
    assert all(x[0] == 'insert' for x in changes)
    assert len(changes) == 2
    added_lines = sum(j2-j1 for tag, i1, i2, j1, j2 in changes)
    assert added_lines == 312
    new_lines = new.splitlines(keepends=True)
    reconstructed = ''.join(''.join(new_lines[j1:j2]) for tag, i1, i2, j1, j2 in ops if tag == 'equal')
    assert reconstructed == base
    shutil.copyfile(SOURCE, HERE / 'R43_CASE8_PADDED_MACRO.asc')
    diff = ''.join(difflib.unified_diff(base.splitlines(keepends=True), new_lines, fromfile='R25_NATIVE_TARGETED.asc', tofile='R43_CASE8_PADDED_MACRO.asc', n=3))
    (HERE / 'R43_vs_R25.diff').write_text(diff, encoding='utf-8', newline='\n')

    helpers = 'namespace bmms83 {\n' + between(new, 'namespace bmms83 {', 'static inline bool NativeEligible') + '}\n'
    macro = 'namespace bmms11r2 {\n' + between(new, 'namespace bmms11r2 {', 'template<class T,bool TA,bool TB>') + '}\n'
    pack = 'namespace bmms_c8p43 {\n' + between(new, 'namespace bmms_c8p43 {', '// Both FP16 and BF16') + '}\n'
    driver = r'''
int main(){
  using namespace bmms_c8p43;
  uint64_t plans=0,layouts=0,invalid=0,maxub=0,maxws=0;
  int minjobs=100000,maxjobs=0;
  uint64_t reduced=0,morePackRounds=0;
  for(int mp=1024;mp<=2048;mp+=16)for(int np=1024;np<=2048;np+=16)
  for(int kp=1056;kp<=1280;kp+=32)for(int cores=1;cores<=64;++cores){
    const int m=mp==1024?mp:mp-1,n=np==1024?np:np-1,k=kp-8;
    auto p=MakePlan(m,n,k,cores,false,false);++plans;
    maxub=std::max(maxub,AppUbBytes(p));maxws=std::max(maxws,WorkspaceBytes(p));
    if(p.cube.blocks<cores)++reduced;
    for(int ta=0;ta<2;++ta)for(int tb=0;tb<2;++tb){
      p=MakePlan(m,n,k,cores,ta,tb);++layouts;
      if(!Eligible(1,m,n,k,1,cores)||!ValidPlan(p,cores))++invalid;
      const int jobs=p.a.jobs+p.b.jobs;
      minjobs=std::min(minjobs,jobs);maxjobs=std::max(maxjobs,jobs);
      const int actual=(jobs+2*p.cube.blocks-1)/(2*p.cube.blocks);
      const int full=(jobs+2*cores-1)/(2*cores);
      if(actual>full)++morePackRounds;
    }
  }
  std::cout << "{\"host_plan_buckets\":"<<plans<<",\"layout_plan_checks\":"<<layouts
    <<",\"invalid\":"<<invalid<<",\"max_explicit_app_ub_bytes\":"<<maxub
    <<",\"max_workspace_bytes\":"<<maxws<<",\"min_pack_jobs_representatives\":"<<minjobs
    <<",\"max_pack_jobs_representatives\":"<<maxjobs<<",\"plans_using_fewer_than_requested_cores\":"<<reduced
    <<",\"layouts_with_more_pack_job_rounds_than_full_cores\":"<<morePackRounds<<"}\n";
  return invalid?1:0;
}
'''
    build = HERE / 'build'
    build.mkdir(exist_ok=True)
    cpp = '#include <cstdint>\n#include <algorithm>\n#include <iostream>\n#define __aicore__\n' + helpers + macro + pack + driver
    (build / 'host.cpp').write_text(cpp, encoding='utf-8', newline='\n')
    compiler = shutil.which('g++')
    assert compiler, 'g++ unavailable; no host analysis was run'
    compile_result = subprocess.run([compiler,'-std=c++17','-O2',str(build/'host.cpp'),'-o',str(build/'host.exe')],capture_output=True,text=True)
    (build/'compile.txt').write_text(compile_result.stdout+compile_result.stderr,encoding='utf-8')
    assert compile_result.returncode == 0, compile_result.stderr
    run = subprocess.run([str(build/'host.exe')],capture_output=True,text=True)
    assert run.returncode == 0, run.stderr
    host = json.loads(run.stdout)

    # All individual M/K and N/K packing geometries in both physical orders.
    # Independent operand coverage is sufficient for DMA row/gap arithmetic;
    # this is not device execution or a proof about cross-core scheduling.
    desc_count=0;job_count=0;extra_gap=0;min_jobs=10**9;max_jobs=0
    max_pad_factor=0.0
    for size in range(1024,2048):
        padded_size=(size+15)//16*16
        for k in range(1032,1280,8):
            pk=(k+31)//32*32
            for sr,sc,dr,dc in [(size,k,padded_size,pk),(k,size,pk,padded_size)]:
                rows_per=32768//dc
                jobs=(dr+rows_per-1)//rows_per
                desc_count+=1;min_jobs=min(min_jobs,jobs);max_jobs=max(max_jobs,jobs)
                pitch=(sc+15)//16*16
                assert (dc-pitch) in (0,16)
                if dc>pitch:extra_gap+=1
                writes=0;reads=0
                for j in range(jobs):
                    row0=j*rows_per;rows=min(rows_per,dr-row0)
                    real_rows=max(0,min(rows,sr-row0))
                    assert 0<rows*dc<=32768 and dc%16==0
                    assert 0<=pitch-sc<=15 and (dc-pitch)%16==0
                    assert row0*dc*2%32==0
                    if real_rows:
                        assert (row0+real_rows)*sc<=sr*sc
                    writes+=rows;reads+=real_rows;job_count+=1
                assert writes==dr and reads==sr
            max_pad_factor=max(max_pad_factor,(padded_size/size)**2*(pk/k))

    result = {
        'scope':'Source diff and extracted host/packing arithmetic only; not CANN compile, device correctness, or timing',
        'source':str(SOURCE),'source_sha256':sha(SOURCE), 'baseline':str(BASE),'baseline_sha256':sha(BASE),
        'only_insertions':True,'added_lines':added_lines,'original_R25_reconstructed_exactly':True,
        'feedback':{'R25_case8_us_approx':91.0,'R43_case8_us':62.45,'other_cases':'User reports basically unchanged, within evaluation fluctuation','raw_15_case_table_available':False,'explicit_full_pass_count':None,'repeat_count':None,'platform_source_hash_verified':False},
        'descriptive_latency_reduction_pct':100*(1-62.45/91),
        'descriptive_speed_ratio':91/62.45,
        'host':host,
        'pack_geometry':{'operand_descriptors':desc_count,'row_jobs_checked':job_count,'descriptors_with_extra_16_word_row_gap':extra_gap,'min_jobs_per_operand':min_jobs,'max_jobs_per_operand':max_jobs},
        'maximum_padded_math_volume_ratio':max_pad_factor,
        'no_Ascend_kernel_modified':True,'no_CANN_compile':True,'no_NPU_run':True,
    }
    (HERE/'ANALYSIS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True))


if __name__=='__main__':
    main()

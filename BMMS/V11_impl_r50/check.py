from pathlib import Path
import json,subprocess,shutil,hashlib
import build as b
H=Path(__file__).resolve().parent;D=H/'cpu_build'
def main():
    b.main();D.mkdir(exist_ok=True)
    shutil.copyfile(b.ROOT/'V11_impl_r49/cpu_build/cpu_shim.hpp',D/'cpu_shim.hpp')
    src=b.BASE.read_text(encoding='utf-8')
    prefix='namespace bmmmaxsum_v43 {\nconstexpr float NEG_INF=-__builtin_inff();\ninline int MinI(int a,int b){return a<b?a:b;}\n'
    prefix+=b.function(src,'static inline bool UseTiny(int32_t M, int32_t N, int32_t K)')+'\n'
    prefix+=b.function(src,'template <typename T, bool TA, bool TB>\n__aicore__ inline void TinyDevice')+'\n}\n'
    prefix+='namespace bmms71 {\ninline int MinI(int a,int b){return a<b?a:b;}\n'
    for mark in ['static inline int32_t Pow2Up(','static inline bool UseResident(','template<class T,bool TA,bool TB>\n__aicore__ inline void ResidentDevice']:
        prefix+=b.function(src,mark)+'\n'
    prefix+='}\nnamespace bmms83 {inline int MinI(int a,int b){return a<b?a:b;}}\n'
    b.write(D/'baseline.hpp',prefix)
    shutil.copyfile(H/'extracted.hpp',D/'extracted.hpp');shutil.copyfile(H/'checks.cpp',D/'checks.cpp')
    args=[shutil.which('g++'),'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-pthread','checks.cpp','-o',str(D/'checks.exe')]
    p=subprocess.run(args,cwd=D,capture_output=True,text=True);b.write(D/'compile.log',p.stdout+p.stderr);assert p.returncode==0,p.stderr[-4000:]
    print('CPU source compiled',flush=True)
    p=subprocess.run([str(D/'checks.exe')],cwd=D,capture_output=True,text=True,timeout=300)
    b.write(D/'run.log',p.stdout+p.stderr);assert p.returncode==0,p.stderr[-4000:]
    result=json.loads(p.stdout)
    good=(D/'extracted.hpp').read_text(encoding='utf-8')
    try:
        b.write(D/'extracted.hpp',b.once(good,'(TA?M:1)*4','1*4'))
        p=subprocess.run(args+['-DFAULT'],cwd=D,capture_output=True,text=True);assert p.returncode==0,p.stderr
        p=subprocess.run([str(D/'checks.exe')],cwd=D,capture_output=True,text=True,timeout=30)
        b.write(D/'bad_gather.log',p.stdout+p.stderr);assert p.returncode!=0 and 'mismatch' in p.stderr,p.stderr
        result['wrong_TA_stride_rejected']=p.stderr.strip()
    finally:b.write(D/'extracted.hpp',good)
    result.update(scope='actual Tiny/Resident and R50 source in CPU arithmetic/storage model; not device pipeline emulation',
                  source_sha256=hashlib.sha256((b.OUT/(b.NAME+'.asc')).read_bytes()).hexdigest(),CANN_compiled=False,NPU_tested=False)
    b.write(b.OUT/'CPU_CHECKS.json',json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':main()

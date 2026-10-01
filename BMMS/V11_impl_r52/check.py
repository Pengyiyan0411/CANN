from pathlib import Path
import json,subprocess,shutil,hashlib
import build as b
H=Path(__file__).resolve().parent;D=H/'cpu_build'
def main():
    b.main();D.mkdir(exist_ok=True)
    shutil.copyfile(b.ROOT/'V11_impl_r50/cpu_build/cpu_shim.hpp',D/'cpu_shim.hpp')
    src=b.BASE.read_text(encoding='utf-8')
    b.write(D/'baseline.hpp','namespace bmmmaxsum_v43 {\n'+b.function(src,'template <typename T>\n__aicore__ inline void DotDevice(')+'\n}\n')
    shutil.copyfile(H/'extracted.hpp',D/'extracted.hpp');shutil.copyfile(H/'checks.cpp',D/'checks.cpp')
    args=[shutil.which('g++'),'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-pthread','checks.cpp']
    p=subprocess.run(args+['-o','checks.exe'],cwd=D,capture_output=True,text=True);b.write(D/'compile.log',p.stdout+p.stderr);assert p.returncode==0,p.stderr[-4000:]
    p=subprocess.run([str(D/'checks.exe')],cwd=D,capture_output=True,text=True,timeout=90)
    b.write(D/'run.log',p.stdout+p.stderr);assert p.returncode==0,p.stderr[-4000:];result=json.loads(p.stdout)
    good=(D/'extracted.hpp').read_text(encoding='utf-8')
    try:
        b.write(D/'extracted.hpp',b.once(good,'2*K);','K);'))
        p=subprocess.run(args+['-DFAULT','-o','fault.exe'],cwd=D,capture_output=True,text=True);assert p.returncode==0,p.stderr
        p=subprocess.run([str(D/'fault.exe')],cwd=D,capture_output=True,text=True,timeout=30)
        b.write(D/'bad_cast.log',p.stdout+p.stderr);assert p.returncode!=0 and 'uninitialized' in p.stderr,p.stderr
        result['incomplete_combined_cast_rejected']=p.stderr.strip()
    finally:b.write(D/'extracted.hpp',good)
    result.update(scope='actual old/new short Dot in CPU arithmetic/storage model, not hardware pipeline emulation',
       source_sha256=hashlib.sha256((b.OUT/(b.NAME+'.asc')).read_bytes()).hexdigest(),CANN_compiled=False,NPU_tested=False)
    b.write(b.OUT/'CPU_CHECKS.json',json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':main()

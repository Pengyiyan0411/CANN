from pathlib import Path
import json,subprocess,shutil,hashlib
import build as b
H=Path(__file__).resolve().parent;D=H/'cpu_build'
def main():
    b.main();D.mkdir(exist_ok=True)
    for name in ['cpu_shim.hpp','baseline.hpp']:
        shutil.copyfile(b.ROOT/'V11_impl_r50/cpu_build'/name,D/name)
    shutil.copyfile(b.ROOT/'V11_impl_r50/extracted.hpp',D/'r50.hpp')
    shutil.copyfile(H/'extracted.hpp',D/'extracted.hpp');shutil.copyfile(H/'checks.cpp',D/'checks.cpp')
    args=[shutil.which('g++'),'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-pthread','checks.cpp']
    p=subprocess.run(args+['-o','checks.exe'],cwd=D,capture_output=True,text=True);b.write(D/'compile.log',p.stdout+p.stderr);assert p.returncode==0,p.stderr[-4000:]
    print('CPU source compiled',flush=True)
    p=subprocess.run([str(D/'checks.exe')],cwd=D,capture_output=True,text=True,timeout=300)
    b.write(D/'run.log',p.stdout+p.stderr);assert p.returncode==0,p.stderr[-4000:]
    result=json.loads(p.stdout)
    good=(D/'extracted.hpp').read_text(encoding='utf-8')
    try:
        b.write(D/'extracted.hpp',b.once(good,'ga[int64_t(batch)*M*K]','ga[0]'))
        p=subprocess.run(args+['-DFAULT','-o','fault.exe'],cwd=D,capture_output=True,text=True);assert p.returncode==0,p.stderr
        p=subprocess.run([str(D/'fault.exe')],cwd=D,capture_output=True,text=True,timeout=30)
        b.write(D/'bad_batch.log',p.stdout+p.stderr);assert p.returncode!=0 and 'mismatch' in p.stderr,p.stderr
        result['wrong_batch_offset_rejected']=p.stderr.strip()
    finally:b.write(D/'extracted.hpp',good)
    result.update(scope='actual Tiny/Resident and R51 source in CPU arithmetic/storage model; workers replayed with ownership checks, not hardware pipeline emulation',
        source_sha256=hashlib.sha256((b.OUT/(b.NAME+'.asc')).read_bytes()).hexdigest(),CANN_compiled=False,NPU_tested=False)
    b.write(b.OUT/'CPU_CHECKS.json',json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':main()

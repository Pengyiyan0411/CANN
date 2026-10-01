from pathlib import Path
import json,shutil,subprocess,hashlib
import build as b
H=Path(__file__).resolve().parent;ROOT=H.parent;D=H/'cpu_build'
def call(args,stem,timeout=600):
    p=subprocess.run(args,cwd=D,capture_output=True,text=True,timeout=timeout)
    b.write(D/(stem+'.log'),p.stdout+p.stderr)
    assert p.returncode==0,(stem,p.returncode,p.stderr[-3000:])
    return p.stdout
def main():
    D.mkdir(exist_ok=True)
    for name in ['cube_model.hpp','cpu_shim.hpp','common_extracted.hpp','ring_extracted.hpp']:
        shutil.copyfile(ROOT/'V11_impl_r49/cpu_build'/name,D/name)
    raw=b.BASE.read_text(encoding='utf-8')
    start=raw.index('// V11 R02:');end=raw.index('// BMMS11R2_CPU_EXTRACT_END',start)
    original=raw[start:end];b.write(D/'ring_extracted.hpp',original+'\n#endif\n')
    shutil.copyfile(H/'extracted.hpp',D/'extracted.hpp');shutil.copyfile(H/'cpu_checks.cpp.in',D/'checks.cpp')
    args=[shutil.which('g++'),'-std=c++20','-O2','-pthread','-fno-fast-math','-ffp-contract=off','checks.cpp']
    exe=D/'checks.exe';call(args+['-o',str(exe)],'compile');print('CPU source harness compiled',flush=True)
    report=json.loads(call([str(exe)],'run',600));print(json.dumps(report),flush=True)
    header=D/'extracted.hpp';good=header.read_text(encoding='utf-8')
    try:
        bad=b.once(good,'uint32_t((TN-nr)*4),0,0','0,0,0');b.write(header,bad)
        exe=D/'fault.exe';call(args+['-DFAULT_PITCH','-o',str(exe)],'fault_compile')
        p=subprocess.run([str(exe)],cwd=D,capture_output=True,text=True,timeout=45);b.write(D/'fault.log',p.stdout+p.stderr)
        assert p.returncode==1 and ('uninitialized' in p.stderr or 'numeric result' in p.stderr),(p.returncode,p.stderr)
        report['wrong_pitch_fault_rejected']=p.stderr.strip()
    finally:b.write(header,good)
    report.update(source_sha256=hashlib.sha256((b.OUT/(b.NAME+'.asc')).read_bytes()).hexdigest(),
        scope='CPU source replay: synthetic macro-ring publisher for large/edge shapes; unchanged actual Cube producer on small M/N with target K and all dtype/transpose bindings; not hardware simulation',
        original_R06_fragment_matches_R52=True,CANN_compiled=False,NPU_tested=False)
    b.write(b.OUT/'CPU_CHECKS.json',json.dumps(report,indent=2)+'\n')
    print('CPU model checks and wrong-pitch fault injection passed',flush=True)
if __name__=='__main__':main()

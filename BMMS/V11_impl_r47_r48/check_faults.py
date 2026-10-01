"""Ensure the new epilogue checks reject consuming invalid N-tail columns."""
import subprocess,shutil,json
import check as c
import build as b
c.prepare()
faults={}
for name,file,old,new,define,expected in [
    ('R47_pad_lanes','r47_extracted.hpp','WholeReduceMax(rows,c,p.N,vr,1,1,p.N/8,','WholeReduceMax(rows,c,TN,vr,1,1,TN/8,','NEGATIVE_PADDING','UB uninitialized read'),
    ('R48_zero_tail','r48_extracted.hpp','Duplicate(c,bmmmaxsum_v43::NEG_INF,mr*TN)','Duplicate(c,0.0f,mr*TN)','NEGATIVE_OWNER','invalid zero padding')]:
    path=c.D/file;original=path.read_text(encoding='utf-8');b.write(path,b.once(original,old,new))
    try:
        exe=c.D/(name+'.exe')
        args=[shutil.which('g++'),'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-pthread','-DCHECK_R01=1','-DCANDIDATE=1','-D'+define,'source_checks.cpp','-o',str(exe)]
        c.call(args,name+'_compile')
        p=subprocess.run([str(exe)],cwd=c.D,capture_output=True,text=True,timeout=45)
        b.write(c.D/(name+'.log'),p.stdout+p.stderr)
        assert p.returncode==1 and expected in p.stderr,(p.returncode,p.stderr)
        faults[name]={'rejected':True,'error':p.stderr.strip()}
    finally:b.write(path,original)
b.write(b.OUT/'FAULT_CHECKS.json',json.dumps(faults,indent=2)+'\n')
print(json.dumps(faults,indent=2))

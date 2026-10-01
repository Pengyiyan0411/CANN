import json,subprocess,shutil,hashlib
import build as b
D=b.H/'cpu_build'
def call(args,name,timeout=600):
    p=subprocess.run(args,cwd=D,capture_output=True,text=True,timeout=timeout)
    b.write(D/(name+'.log'),p.stdout+p.stderr)
    assert p.returncode==0,(name,p.returncode,p.stderr[-2500:]);return p.stdout
def main():
    D.mkdir(exist_ok=True)
    for f in ['cpu_shim.hpp','cube_model.hpp','common_extracted.hpp','ring_extracted.hpp']:shutil.copyfile(b.ROOT/'V12_impl_r01/cpu_build'/f,D/f)
    shutil.copyfile(b.H/'extracted.hpp',D/'extracted.hpp')
    s=(b.ROOT/'V12_impl_r02_r03/cpu_r02/checks.cpp').read_text().replace('bmms1202','bmms1204').replace('ResidentAProducer','CachedAProducer')
    s=b.once(s,'uint64_t(p.B)*p.M*p.K*2*(compact?p.pN:p.nTiles)','uint64_t(p.B)*p.M*2*(compact?512*p.pN+(p.K-512)*p.nTiles:p.K*p.nTiles)')
    a=s.index('        if(compact){newA+=');z=s.index('        reduceRows+=',a)
    s=s[:a]+'''        const uint64_t baseCopies=uint64_t(p.B)*p.mTiles*p.nTiles*((p.K+255)/256);
        const uint64_t newACopies=baseCopies-uint64_t(p.B)*p.mTiles*(p.nTiles-p.pN)*2;
        Mock::need(TrafficAB::bCopies==baseCopies,"B descriptor count changed");
        Mock::need(TrafficAB::aCopies==(compact?newACopies:baseCopies),"A descriptor count mismatch");
        if(compact){newA+=TrafficAB::aBytes;newB+=TrafficAB::bBytes;newAC+=TrafficAB::aCopies;newBC+=TrafficAB::bCopies;}
        else{oldA+=TrafficAB::aBytes;oldB+=TrafficAB::bBytes;oldAC+=TrafficAB::aCopies;oldBC+=TrafficAB::bCopies;}
'''+s[z:]
    s=s.replace('uint64_t oldA=','uint64_t oldAC=0,newAC=0,oldBC=0,newBC=0;\nuint64_t oldA=')
    s=s.replace('    Mock::need(newA<oldA', '    pair<half,false,true>(1,144,272,1024,1,1,1);\n    pair<bfloat16_t,true,false>(1,16,784,1280);\n    Mock::need(newA<oldA')
    s=s.replace('<<",\\"ring_reads_elements\\":"', '<<",\\"old_A_descriptors\\":"<<oldAC<<",\\"new_A_descriptors\\":"<<newAC<<",\\"old_B_descriptors\\":"<<oldBC<<",\\"new_B_descriptors\\":"<<newBC<<",\\"ring_reads_elements\\":"')
    b.write(D/'checks.cpp',s)
    args=[shutil.which('g++'),'-std=c++20','-O2','-pthread','-fno-fast-math','-ffp-contract=off','checks.cpp']
    exe=D/'checks.exe';call(args+['-o',str(exe)],'compile');print('r04 CPU compiled',flush=True)
    report=json.loads(call([str(exe)],'run'));print(report,flush=True)
    header=D/'extracted.hpp';good=header.read_text()
    try:
        # Cached slots must be read for kBase<512, not the rotating stream slots.
        b.write(header,b.once(good,'(s1+(kBase<CACHE_K?2:0))*AM*K1','s1*AM*K1'))
        exe=D/'fault.exe';call(args+['-DFAULT','-o',str(exe)],'fault_compile')
        p=subprocess.run([str(exe)],cwd=D,capture_output=True,text=True,timeout=90)
        b.write(D/'fault.log',p.stdout+p.stderr)
        assert p.returncode==1 and ('numeric result' in p.stderr or 'uninitialized' in p.stderr),(p.returncode,p.stderr)
        report['wrong_cache_slot_rejected']=p.stderr.strip()
    finally:b.write(header,good)
    report.update(source_sha256=hashlib.sha256((b.OUT/(b.NAME+'.asc')).read_bytes()).hexdigest(),CANN_compiled=False,NPU_tested=False,scope='actual original and partial-A-cache producer plus unchanged consumer; full target K on small spatial CPU fixtures; logical descriptor counters are not timings')
    b.write(b.OUT/'v12_r04_cpu_checks.json',json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()

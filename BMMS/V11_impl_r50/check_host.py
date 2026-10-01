"""Compare actual R49/R50 dispatch with launch-recording stubs."""
from pathlib import Path
import json,re,shutil,subprocess,hashlib
import build as b
H=Path(__file__).resolve().parent;ROOT=H.parent;D=H/'host_build'
def main():
    D.mkdir(exist_ok=True)
    s=(ROOT/'V11_impl_r49/host_build/host.cpp').read_text(encoding='utf-8').split('#define BMMS23_SINGLE_K_CONTROL')[0]
    base=b.BASE.read_text(encoding='utf-8')
    s+='namespace bmms71 {\n'+b.function(base,'static inline int32_t Pow2Up(')+'\n}\n'
    fragment=b.module()
    s+=fragment[:fragment.index('// Batch the independent row work')].replace('// BMMS50_BEGIN','')+'}\n'
    binds=re.findall(r'^BMMS50_KERNEL\((\w+),(\w+),(true|false),(true|false)\)$',fragment,re.M);assert len(binds)==8
    for fn,T,ta,tb in binds:
        dt=1 if T=='half' else 2
        s+=f'void {fn}(GM_ADDR,GM_ADDR,GM_ADDR,bmms50::Plan p){{actual.dt={dt};actual.ta={ta};actual.tb={tb};actual.strategy=50;actual.plan={{1,p.M,p.N,p.K,p.kp,p.tiny,0,0,0,1}};++actual.launches;}}\n'
    for i,path in enumerate([b.BASE,b.OUT/(b.NAME+'.asc')]):
        code=path.read_text(encoding='utf-8')
        s+=f'#define BMMS23_SINGLE_K_CONTROL 0\n#define BMMS25_SMALL 1\n#define BMMS25_DENSE 1\nnamespace V{i} {{\n'
        for ns in ['bmms11r2','bmms11d','bmms23','bmms_c8p43','bmms48','bmms49']+(['bmms50'] if i else []):
            s+=f'namespace {ns} {{using namespace ::{ns};\n'+b.host(code,ns)+'\n}\n'
        s+='namespace bmms25 {using namespace ::bmms83;\n'+b.function(code,'static inline int Select(')+'\n'+b.host(code,'bmms25')+'\n}\n'
        s+=b.function(code,'extern "C" void run_kernel(').replace('extern "C" void run_kernel','void run')+'\n}\n#undef BMMS23_SINGLE_K_CONTROL\n#undef BMMS25_SMALL\n#undef BMMS25_DENSE\n'
    for plan in ['p','p.cube']:s=s.replace(f'NAME<<<{plan}.blocks,nullptr,stream>>>',f'recordBlocks({plan}.blocks), NAME')
    s=s.replace('NAME<<<p.workers,nullptr,stream>>>','recordBlocks(p.workers), NAME').replace('NAME<<<1,nullptr,stream>>>','recordBlocks(1), NAME');assert '<<<' not in s
    s+='using Run=void(*)(GM_ADDR,const TensorGroupInfo&,GM_ADDR,const TensorGroupInfo&,GM_ADDR,const TensorGroupInfo&,int64_t,aclrtStream,bool,bool);\nRun functions[]={V0::run,V1::run};\n'
    s+=(H/'host_checks.cpp.in').read_text(encoding='utf-8');b.write(D/'host.cpp',s)
    c=subprocess.run([shutil.which('g++'),'-std=c++20','-O2',str(D/'host.cpp'),'-o',str(D/'host.exe')],capture_output=True,text=True)
    b.write(D/'compile.log',c.stdout+c.stderr);assert c.returncode==0,c.stderr[-5000:]
    p=subprocess.run([str(D/'host.exe')],capture_output=True,text=True,timeout=180)
    b.write(D/'run.log',p.stdout+p.stderr);assert p.returncode==0,p.stderr
    r=json.loads(p.stdout);r.update(scope='actual run_kernel/TryLaunch with recording stubs; original fallback device covered separately by CPU_CHECKS',source_sha256=hashlib.sha256((b.OUT/(b.NAME+'.asc')).read_bytes()).hexdigest(),CANN_compiled=False,NPU_tested=False)
    b.write(b.OUT/'HOST_CHECKS.json',json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
if __name__=='__main__':main()

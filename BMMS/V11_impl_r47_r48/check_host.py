"""Replay real R43/R47/R48 run_kernel and TryLaunch with recording launch stubs."""
from pathlib import Path
import json,re,shutil,subprocess
import build as b
H=Path(__file__).resolve().parent;ROOT=H.parent;D=H/'host_build'
def main():
    D.mkdir(exist_ok=True)
    base=b.BASE.read_text(encoding='utf-8')
    s=(ROOT/'V11_native_targeted25/host_build/host.cpp').read_text(encoding='utf-8').split('#define BMMS23_SINGLE_K_CONTROL')[0]
    s=s.replace('TREE,FALLBACK};','TREE,FALLBACK,PADDED};')
    s+=b.between(base,'namespace bmms_c8p43 {','// BMMS_C8P43_HOST_MODEL_END')+'}\n'
    for n in [47,48]:
        frag=(b.OUT/(b.NAMES[n]+'.asc')).read_text(encoding='utf-8').split(f'// BMMS{n}_BEGIN')[1]
        marker='template<class T,bool TA,bool TB,int TK>' if n==47 else '// A Cube group owns'
        s+=frag[:frag.index(marker)]+'}\n'
    for n,prefix,macro,route in [(43,'bmms_c8p43','BMMS_C8P43','PADDED'),(47,'bmms47','BMMS47','NATIVE'),(48,'bmms48','BMMS48','RESIDUAL')]:
        code=base if n==43 else (b.OUT/(b.NAMES[n]+'.asc')).read_text(encoding='utf-8')
        binds=re.findall(r'^'+macro+r'_KERNEL\((\w+),(\w+),(true|false),(true|false)\)$',code,re.M);assert len(binds)==8
        for fn,T,ta,tb in binds:
            dt=1 if T=='half' else 2
            args='GM_ADDR,GM_ADDR,GM_ADDR,GM_ADDR,GM_ADDR,GM_ADDR,GM_ADDR part,'+prefix+'::RaggedPlan p' if n==43 else 'GM_ADDR,GM_ADDR,GM_ADDR,GM_ADDR,GM_ADDR part,'+prefix+'::Plan p'
            s+=f'void {fn}({args}){{nativeRecord({route},{dt},{ta},{tb},part,'+('p.cube' if n==43 else 'p')+f');actual.strategy={n};'+('actual.partial=0;' if n==48 else '')+'}\n'
    for i,file in enumerate([b.BASE]+[b.OUT/(v+'.asc') for v in b.NAMES.values()]):
        code=file.read_text(encoding='utf-8')
        s+=f'#define BMMS23_SINGLE_K_CONTROL 0\n#define BMMS25_SMALL 1\n#define BMMS25_DENSE 1\nnamespace V{i} {{\n'
        for ns in ['bmms11r2','bmms11d','bmms23','bmms_c8p43']+([f'bmms{i+46}'] if i else []):
            s+=f'namespace {ns} {{using namespace ::{ns};\n'+b.host(code,ns)+'\n}\n'
        s+='namespace bmms25 {using namespace ::bmms83;\n'+b.function(code,'static inline int Select(')+'\n'+b.host(code,'bmms25')+'\n}\n'
        s+=b.function(code,'extern "C" void run_kernel(').replace('extern "C" void run_kernel','void run')+'\n}\n#undef BMMS23_SINGLE_K_CONTROL\n#undef BMMS25_SMALL\n#undef BMMS25_DENSE\n'
    for plan in ['p','p.cube']:
        s=s.replace(f'NAME<<<{plan}.blocks,nullptr,stream>>>',f'recordBlocks({plan}.blocks), NAME')
    s=s.replace('NAME<<<p.workers,nullptr,stream>>>','recordBlocks(p.workers), NAME');assert '<<<' not in s
    s+='using Run=void(*)(GM_ADDR,const TensorGroupInfo&,GM_ADDR,const TensorGroupInfo&,GM_ADDR,const TensorGroupInfo&,int64_t,aclrtStream,bool,bool);\nRun functions[]={V0::run,V1::run,V2::run};\n'
    s+=(H/'host_checks.cpp.in').read_text(encoding='utf-8');b.write(D/'host.cpp',s)
    c=subprocess.run([shutil.which('g++'),'-std=c++20','-O2',str(D/'host.cpp'),'-o',str(D/'host.exe')],capture_output=True,text=True)
    b.write(D/'compile.log',c.stdout+c.stderr);assert c.returncode==0,c.stderr[-5000:]
    p=subprocess.run([str(D/'host.exe')],capture_output=True,text=True,timeout=180)
    b.write(D/'run.log',p.stdout+p.stderr);assert p.returncode==0,p.stderr
    result=json.loads(p.stdout);result.update(scope='actual host dispatch and launch/allocation records; device calls recorded, not executed',CANN_compiled=False,NPU_tested=False)
    b.write(b.OUT/'HOST_CHECKS.json',json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()

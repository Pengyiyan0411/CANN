from pathlib import Path
import json,re,shutil,subprocess,hashlib
import build as b
H=Path(__file__).resolve().parent;D=H/'host_build'

def main():
    D.mkdir(exist_ok=True)
    s=(b.ROOT/'V11_impl_r52/host_build/host.cpp').read_text(encoding='utf-8').split('#define BMMS23_SINGLE_K_CONTROL')[0]
    src=(b.OUT/'V12_BASELINE_R52.asc').read_text(encoding='utf-8')
    m2=b.module(src);m3=b.previous.module3(src)
    s+=m2[:m2.index('template<class T,bool TA,bool TB>')]+ '}\n'
    s+=m3[:m3.index('template<class T,bool TA,bool TB,int K>')]+ '}\n'
    binds=re.findall(r'^BMMS1206_KERNEL\((\w+),(\w+),(true|false),(true|false)\)$',m2,re.M);assert len(binds)==8
    for fn,T,ta,tb in binds:
        dt=1 if T=='half' else 2
        s+=f'void {fn}(GM_ADDR,GM_ADDR,GM_ADDR,GM_ADDR,GM_ADDR part,bmms1206::Plan p){{nativeRecord(MACRO,{dt},{ta},{tb},part,p);actual.strategy=1206;}}\n'
    binds=re.findall(r'^BMMS1203_KERNEL\((\w+),(\w+),(true|false),(true|false),(\d+)\)$',m3,re.M);assert len(binds)==104
    for fn,T,ta,tb,k in binds:
        dt=1 if T=='half' else 2
        s+=f'void {fn}(GM_ADDR a,GM_ADDR bb,GM_ADDR y,bmms1203::Plan p){{need(p.K=={k},"static K binding mismatch");bmms50_{"f16" if dt==1 else "b16"}_{"t" if ta=="true" else "n"}{"t" if tb=="true" else "n"}(a,bb,y,p);actual.strategy=1203;}}\n'
    for i,path in enumerate([b.OUT/'V12_BASELINE_R52.asc',b.OUT/(b.NAME+'.asc'),b.BASE]):
        code=path.read_text(encoding='utf-8')
        s+=f'#define BMMS23_SINGLE_K_CONTROL 0\n#define BMMS25_SMALL 1\n#define BMMS25_DENSE 1\nnamespace V{i} {{\n'
        for ns in ['bmms11r2','bmms11d','bmms23','bmms_c8p43','bmms48','bmms49','bmms50','bmms52']+(['bmms1203','bmms1206'] if i==1 else ['bmms1203'] if i==2 else []):
            s+=f'namespace {ns} {{using namespace ::{ns};\n'+b.host(code,ns)+'\n}\n'
        s+='namespace bmms25 {using namespace ::bmms83;\n'+b.function(code,'static inline int Select(')+'\n'+b.host(code,'bmms25')+'\n}\n'
        s+=b.function(code,'extern "C" void run_kernel(').replace('extern "C" void run_kernel','void run')+'\n}\n#undef BMMS23_SINGLE_K_CONTROL\n#undef BMMS25_SMALL\n#undef BMMS25_DENSE\n'
    for plan in ['p','p.cube']:s=s.replace(f'NAME<<<{plan}.blocks,nullptr,stream>>>',f'recordBlocks({plan}.blocks), NAME')
    s=s.replace('NAME<<<p.workers,nullptr,stream>>>','recordBlocks(p.workers), NAME').replace('NAME<<<1,nullptr,stream>>>','recordBlocks(1), NAME');assert '<<<' not in s
    s+='using Run=void(*)(GM_ADDR,const TensorGroupInfo&,GM_ADDR,const TensorGroupInfo&,GM_ADDR,const TensorGroupInfo&,int64_t,aclrtStream,bool,bool);\nRun functions[]={V0::run,V1::run,V2::run};\n'
    s+=(H/'host_checks.cpp.in').read_text(encoding='utf-8')
    s=s.replace('if(!p)throw std::runtime_error(s);','if(!p){std::cerr<<s<<std::endl;std::exit(1);}')
    b.write(D/'host.cpp',s)
    c=subprocess.run([shutil.which('g++'),'-std=c++20','-O2',str(D/'host.cpp'),'-o',str(D/'host.exe')],capture_output=True,text=True)
    b.write(D/'compile.log',c.stdout+c.stderr);assert c.returncode==0,c.stderr[-5000:]
    p=subprocess.run([str(D/'host.exe')],capture_output=True,text=True,timeout=180)
    b.write(D/'run.log',p.stdout+p.stderr);assert p.returncode==0,(p.returncode,p.stderr)
    r=json.loads(p.stdout);r.update(scope='actual host dispatch with recording kernel stubs; no device compilation',CANN_compiled=False,NPU_tested=False)
    r['source_sha256']=hashlib.sha256((b.OUT/(b.NAME+'.asc')).read_bytes()).hexdigest();r['parent_sha256']=b.SHA
    b.write(b.OUT/'v12_r06_host_checks.json',json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
if __name__=='__main__':main()

import re,json,subprocess,shutil,hashlib
import build as b
D=b.H/'host_build'

def main():
    D.mkdir(exist_ok=True)
    # Recording stubs and preserved V0=R52, V2=r03 from the audited r04 harness.
    s=(b.ROOT/'V12_impl_r04/host_build/host.cpp').read_text()
    start=s.index('namespace V1 {');end=s.index('#undef BMMS25_DENSE',start)+len('#undef BMMS25_DENSE')
    code=(b.OUT/(b.NAME+'.asc')).read_text()
    lane='namespace V1 {\n'
    for ns in ['bmms11r2','bmms11d','bmms23','bmms_c8p43','bmms48','bmms49','bmms50','bmms52','bmms1203']:
        lane+=f'namespace {ns} {{using namespace ::{ns};\n'+b.host(code,ns)+'\n}\n'
    lane+='namespace bmms25 {using namespace ::bmms83;\n'+b.function(code,'static inline int Select(')+'\n'+b.host(code,'bmms25')+'\n}\n'
    lane+=b.function(code,'extern "C" void run_kernel(').replace('extern "C" void run_kernel','void run')+'\n}\n#undef BMMS23_SINGLE_K_CONTROL\n#undef BMMS25_SMALL\n#undef BMMS25_DENSE'
    for plan in ['p','p.cube']:lane=lane.replace(f'NAME<<<{plan}.blocks,nullptr,stream>>>',f'recordBlocks({plan}.blocks), NAME')
    lane=lane.replace('NAME<<<p.workers,nullptr,stream>>>','recordBlocks(p.workers), NAME').replace('NAME<<<1,nullptr,stream>>>','recordBlocks(1), NAME')
    assert '<<<' not in lane
    s=s[:start]+lane+s[end:]
    a=s.index('    auto want2=parent;');z=s.index('    const bool hit3=',a)
    s=s[:a]+'''    auto want2=parent;
    if(hit2){
        need(parent.route==MACRO,"probe not originally R06");
        auto p=bmms11r2::MakePlan(B,M,N,K,c);
        p.pM=1;p.pN=1;p.tasks=B;p.blocks=1;
        want2.blocks=1;want2.plan={B,M,N,K,p.mTiles,p.nTiles,1,1,B,1};
        want2.allocation=bmms11r2::WorkspaceBytes(p);want2.partial=bmms11r2::RingBytes(p);
        uint64_t area=0;
        for(int batch=0;batch<B;++batch)for(int mt=0;mt<p.mTiles;++mt)for(int nt=0;nt<p.nTiles;++nt)
            area+=uint64_t(std::min(128,M-mt*128))*std::min(256,N-nt*256);
        need(area==uint64_t(B)*M*N,"stress plan dropped work");
        ++hits2;
    }else ++unchanged2;
'''+s[z:]
    s=s.replace('r04','r05')
    b.write(D/'host.cpp',s)
    p=subprocess.run([shutil.which('g++'),'-std=c++20','-O2',str(D/'host.cpp'),'-o',str(D/'host.exe')],capture_output=True,text=True)
    b.write(D/'compile.log',p.stdout+p.stderr);assert p.returncode==0,p.stderr[-3000:]
    p=subprocess.run([str(D/'host.exe')],capture_output=True,text=True,timeout=180)
    b.write(D/'run.log',p.stdout+p.stderr);assert p.returncode==0,(p.returncode,p.stderr)
    r=json.loads(p.stdout);r.update(source_sha256=hashlib.sha256((b.OUT/(b.NAME+'.asc')).read_bytes()).hexdigest(),parent_sha256=b.SHA,scope='actual host dispatch with recording stubs; stress plan coverage/workspace checks; target predicate matches original r04 predicate before plan mutation',CANN_compiled=False,NPU_tested=False)
    b.write(b.OUT/'v12_r05_host_checks.json',json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
if __name__=='__main__':main()

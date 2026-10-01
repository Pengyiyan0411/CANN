from pathlib import Path
import json,subprocess,shutil,hashlib
import build as b
H=b.H;ROOT=b.ROOT;OUT=b.OUT
def call(args,D,name,timeout=600):
    p=subprocess.run(args,cwd=D,capture_output=True,text=True,timeout=timeout)
    b.write(D/(name+'.log'),p.stdout+p.stderr)
    assert p.returncode==0,(name,p.returncode,p.stderr[-3000:]);return p.stdout
def small():
    D=H/'cpu_r03';D.mkdir(exist_ok=True)
    for f in ['cpu_shim.hpp','baseline.hpp']:shutil.copyfile(ROOT/'V11_impl_r50/cpu_build'/f,D/f)
    shutil.copyfile(ROOT/'V11_impl_r50/extracted.hpp',D/'r50.hpp');shutil.copyfile(H/'r03_extracted.hpp',D/'extracted.hpp')
    s=(ROOT/'V11_impl_r50/checks.cpp').read_text(encoding='utf-8')
    s=s.replace('#include "extracted.hpp"','#include "r50.hpp"\n#include "extracted.hpp"')
    dispatch='template<class T,bool A,bool B>void candidate(GM_ADDR a,GM_ADDR b,GM_ADDR y,bmms50::Plan p){switch(p.K){\n'
    for k in range(32,129,8):dispatch+=f'case {k}:bmms1203::Device<T,A,B,{k}>(a,b,y,p);return;\n'
    dispatch+='}throw std::runtime_error("invalid K");}\n'
    s=s.replace('int runs=0,',dispatch+'int runs=0,')
    a=s.index('        if(mode)');z=s.index('        Mock::need(ctx.barrier',a)
    s=s[:a]+'''        if(mode)candidate<T,TA,TB>((GM_ADDR)a.data(),(GM_ADDR)b.data(),(GM_ADDR)&results[mode],p);
        else bmms50::Device<T,TA,TB>((GM_ADDR)a.data(),(GM_ADDR)b.data(),(GM_ADDR)&results[mode],p);
'''+s[z:]
    s=s.replace('run<half,true,false>(3,5,72,0)','run<half,true,false>(3,5,64,0)')
    b.write(D/'checks.cpp',s)
    args=[shutil.which('g++'),'-std=c++20','-O2','-pthread','-fno-fast-math','-ffp-contract=off','checks.cpp']
    exe=D/'checks.exe';call(args+['-o',str(exe)],D,'compile');print('r03 CPU compiled',flush=True)
    report=json.loads(call([str(exe)],D,'run'));print(report,flush=True)
    header=D/'extracted.hpp';good=header.read_text(encoding='utf-8')
    try:
        b.write(header,b.once(good,'DIRECT_A=!TA&&K==kp','DIRECT_A=K==kp'))
        exe=D/'fault.exe';call(args+['-DFAULT','-o',str(exe)],D,'fault_compile')
        p=subprocess.run([str(exe)],cwd=D,capture_output=True,text=True,timeout=40)
        b.write(D/'fault.log',p.stdout+p.stderr);assert p.returncode==1 and 'mismatch' in p.stderr,(p.returncode,p.stderr)
        report['wrong_contiguous_alias_rejected']=p.stderr.strip()
    finally:b.write(header,good)
    report.update(source_sha256=hashlib.sha256((OUT/(b.NAMES[3]+'.asc')).read_bytes()).hexdigest(),CANN_compiled=False,NPU_tested=False,scope='actual old R50 and new static-K vector source on CPU adapters')
    b.write(OUT/'v12_r03_cpu_checks.json',json.dumps(report,indent=2)+'\n')
def dense():
    D=H/'cpu_r02';D.mkdir(exist_ok=True)
    for f in ['cpu_shim.hpp','cube_model.hpp','common_extracted.hpp','ring_extracted.hpp']:shutil.copyfile(ROOT/'V12_impl_r01/cpu_build'/f,D/f)
    shutil.copyfile(H/'r02_extracted.hpp',D/'extracted.hpp')
    s=(ROOT/'V12_impl_r01/cpu_checks.cpp.in').read_text(encoding='utf-8').replace('bmms1201::Plan','bmms1202::Plan')
    a=s.index('            if(Mock::cube)');z=s.index('        },reverse);',a)
    s=s[:a]+'''            if(Mock::cube){
                if(compact){bmms1202::ResidentAProducer<T,TA,TB> op;op.Init((GM_ADDR)a.data(),(GM_ADDR)b.data(),(GM_ADDR)ws.data(),p,&pipe);op.Process();}
                else{bmms11r2::ReuseProducer<T,TA,TB> op;op.Init((GM_ADDR)a.data(),(GM_ADDR)b.data(),(GM_ADDR)ws.data(),p,&pipe);op.Process();}
            }else{bmms11r2::RowMaxConsumer op;op.Init((GM_ADDR)ws.data(),(GM_ADDR)part,(GM_ADDR)y.data(),p,&pipe);op.Process();}
'''+s[z:]
    a=s.index('        if(compact){Mock::need(OpStats::duplicateElements');z=s.index('        reduceRows+=',a)
    s=s[:a]+'''        const uint64_t expectedA=uint64_t(p.B)*p.M*p.K*2*(compact?p.pN:p.nTiles);
        const uint64_t expectedB=uint64_t(p.B)*p.N*p.K*2*p.mTiles;
        Mock::need(TrafficAB::aBytes==expectedA&&TrafficAB::bBytes==expectedB,"operand traffic mismatch");
        Mock::need(Traffic::mmads==uint64_t(p.B)*((p.M+63)/64)*((p.N+127)/128)*((p.K+63)/64),"MMAD arithmetic changed");
        if(compact){newA+=TrafficAB::aBytes;newB+=TrafficAB::bBytes;}else{oldA+=TrafficAB::aBytes;oldB+=TrafficAB::bBytes;}
'''+s[z:]
    s=s.replace('uint64_t runs=0,','uint64_t oldA=0,newA=0,oldB=0,newB=0;\nuint64_t runs=0,')
    s=s[:s.index('void pair(Plan p,')]+'''
template<class T,bool A,bool B>void pair(int batch,int M,int N,int K,int pm=1,int pn=1,int blocks=1){
    auto p=custom(batch,M,N,pm,pn,blocks);p.K=K;
    auto x=run<T,A,B>(p,false,0,false,true),y=run<T,A,B>(p,true,0,true,true);Mock::need(x==y,"old/new producer differs");
}
int main(){try{
#ifdef FAULT
    pair<half,true,false>(1,16,272,1056);return 7;
#endif
    pair<half,false,false>(1,16,272,1056);pair<half,false,true>(1,16,272,1056);
    pair<half,true,false>(1,16,272,1056);pair<half,true,true>(1,16,272,1056);
    pair<bfloat16_t,false,false>(1,16,272,1056);pair<bfloat16_t,false,true>(1,16,272,1056);
    pair<bfloat16_t,true,false>(1,16,272,1056);pair<bfloat16_t,true,true>(1,16,272,1056);
    pair<half,false,false>(1,144,272,1024,2,1,2);pair<bfloat16_t,true,true>(1,144,272,1024,2,1,2);
    pair<half,true,false>(1,16,528,1504,1,2,2);pair<bfloat16_t,false,true>(1,16,528,1504,1,2,2);
    pair<half,true,true>(3,16,272,1088,1,1,2);
    Mock::need(newA<oldA&&newB==oldB,"resident traffic not reduced");
    std::cout<<"{\\"source_runs\\":"<<runs<<",\\"bitwise_equal_pairs\\":"<<runs/2<<",\\"old_A_bytes\\":"<<oldA<<",\\"new_A_bytes\\":"<<newA
      <<",\\"old_B_bytes\\":"<<oldB<<",\\"new_B_bytes\\":"<<newB<<",\\"ring_reads_elements\\":"<<reads<<",\\"ready_publications\\":"<<credits<<",\\"arena_peak_bytes\\":[";
    for(int i=0;i<5;++i){if(i)std::cout<<",";std::cout<<OpStats::peak[i];}std::cout<<"]}\\n";
}catch(const std::exception&e){std::cerr<<e.what()<<std::endl;return 1;}}
'''
    b.write(D/'checks.cpp',s);args=[shutil.which('g++'),'-std=c++20','-O2','-pthread','-fno-fast-math','-ffp-contract=off','checks.cpp'];exe=D/'checks.exe'
    call(args+['-o',str(exe)],D,'compile');print('r02 CPU compiled',flush=True)
    report=json.loads(call([str(exe)],D,'run'));print(report,flush=True)
    header=D/'extracted.hpp';good=header.read_text(encoding='utf-8')
    try:
        b.write(header,b.once(good,'const int ak=kBase+kk;','const int ak=kk;'))
        exe=D/'fault.exe';call(args+['-DFAULT','-o',str(exe)],D,'fault_compile')
        p=subprocess.run([str(exe)],cwd=D,capture_output=True,text=True,timeout=90);b.write(D/'fault.log',p.stdout+p.stderr)
        assert p.returncode==1 and ('numeric result' in p.stderr or 'uninitialized' in p.stderr),(p.returncode,p.stderr)
        report['missing_resident_K_offset_rejected']=p.stderr.strip()
    finally:b.write(header,good)
    report.update(source_sha256=hashlib.sha256((OUT/(b.NAMES[2]+'.asc')).read_bytes()).hexdigest(),CANN_compiled=False,NPU_tested=False,
      scope='actual original and resident-A producer plus unchanged consumer on small spatial CPU fixtures with full target K; no full-size NPU execution')
    b.write(OUT/'v12_r02_cpu_checks.json',json.dumps(report,indent=2)+'\n')
if __name__=='__main__':
    import sys
    if len(sys.argv)==1 or sys.argv[1]=='3':small()
    if len(sys.argv)==1 or sys.argv[1]=='2':dense()

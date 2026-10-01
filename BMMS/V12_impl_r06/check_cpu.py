import json,subprocess,shutil,hashlib
import build as b
D=b.H/'cpu_build'
def call(args,name,timeout=600):
    p=subprocess.run(args,cwd=D,capture_output=True,text=True,timeout=timeout)
    b.write(D/(name+'.log'),p.stdout+p.stderr);assert p.returncode==0,(name,p.returncode,p.stderr[-2500:]);return p.stdout
def main():
    D.mkdir(exist_ok=True)
    for f in ['cpu_shim.hpp','cube_model.hpp','common_extracted.hpp','ring_extracted.hpp']:shutil.copyfile(b.ROOT/'V12_impl_r01/cpu_build'/f,D/f)
    shutil.copyfile(b.H/'extracted.hpp',D/'extracted.hpp')
    s=(b.ROOT/'V12_impl_r04/cpu_build/checks.cpp').read_text().replace('bmms1204','bmms1206').replace('CachedAProducer','MacroMmadProducer')
    s=s.replace('uint64_t oldAC=','uint64_t oldMM=0,newMM=0,oldL0B=0,newL0B=0;double maxRelative=0;\nuint64_t oldAC=')
    s=s.replace('Traffic::reset();','Traffic::reset();NativeTraffic::reset();')
    a=s.index('    if(real){for(size_t');z=s.index('    std::vector<uint32_t> gold;',a)
    s=s[:a]+'''    auto sample=[](size_t i,unsigned seed){unsigned h=unsigned(i)^seed;h^=h>>16;h*=0x7feb352du;h^=h>>15;h*=0x846ca68bu;h^=h>>16;
        return std::ldexp(float(int(h%8191)-4095)/1024,int((h>>16)%13)-6);};
    if(real){for(size_t i=0;i<a.size();++i){float x=sample(i,74191);a[i]=T(pattern==2?0:pattern==1?-std::abs(x):x);}
        for(size_t i=0;i<b.size();++i){float x=sample(i,99239);b[i]=T(pattern==1?std::abs(x):x);}}
    std::vector<double> exact(p.B,0);
'''+s[z:]
    s=s.replace('for(int z=0;z<p.B;++z){std::vector<float> rows(p.M,-INFINITY);','for(int z=0;z<p.B;++z){std::vector<float> rows(p.M,-INFINITY);std::vector<double> exactRows(p.M,-INFINITY);')
    s=s.replace('if(real){v=0;for(int k=0;k<p.K;++k)v+=float(a[ai(z,m,k)])*float(b[bi(z,k,n)]);}',
        'if(real){v=0;double ev=0;for(int k=0;k<p.K;++k){const float av=float(a[ai(z,m,k)]),bv=float(b[bi(z,k,n)]);v+=av*bv;ev+=double(av)*bv;}exactRows[m]=std::max(exactRows[m],ev);}')
    s=s.replace('}gold.push_back(std::bit_cast<uint32_t>(AscendC::sumtree(rows)));','}for(double v:exactRows)exact[z]+=v;gold.push_back(std::bit_cast<uint32_t>(AscendC::sumtree(rows)));')
    a=s.index('        const uint64_t expectedA=');z=s.index('        reduceRows+=',a)
    s=s[:a]+'''        for(int batch=0;batch<p.B;++batch){double err=std::abs(double(y[batch])-exact[batch])/std::max(1.0,std::abs(exact[batch]));maxRelative=std::max(maxRelative,err);Mock::need(err<=1e-4,"FP64 reference error too large");}
        const uint64_t expectedA=uint64_t(p.B)*p.M*p.K*2*p.nTiles,expectedB=uint64_t(p.B)*p.N*p.K*2*p.mTiles;
        Mock::need(TrafficAB::aBytes==expectedA&&TrafficAB::bBytes==expectedB,"GM operand traffic changed");
        Mock::need(Traffic::l0Bytes==expectedA+expectedB,"L0 operand bytes changed");
        const uint64_t expectedMM=uint64_t(p.B)*(compact?p.mTiles:((p.M+63)/64))*(compact?p.nTiles:((p.N+127)/128))*((p.K+63)/64);
        Mock::need(Traffic::mmads==expectedMM,"MMAD count not reduced as designed");
        const uint64_t copies=uint64_t(p.B)*p.mTiles*p.nTiles*((p.K+255)/256);
        Mock::need(TrafficAB::aCopies==copies&&TrafficAB::bCopies==copies,"GM descriptors changed");
        Mock::need(NativeTraffic::b0Calls==uint64_t(p.B)*p.mTiles*(compact?p.nTiles:(p.N+127)/128)*(p.K/16),"L0B descriptor count wrong");
        if(compact){newA+=TrafficAB::aBytes;newB+=TrafficAB::bBytes;newMM+=Traffic::mmads;newL0B+=NativeTraffic::b0Calls;}
        else{oldA+=TrafficAB::aBytes;oldB+=TrafficAB::bBytes;oldMM+=Traffic::mmads;oldL0B+=NativeTraffic::b0Calls;}
'''+s[z:]
    s=s.replace('int pm=1,int pn=1,int blocks=1){','int pm=1,int pn=1,int blocks=1,int pattern=0){')
    s=s.replace('run<T,A,B>(p,false,0,false,true),y=run<T,A,B>(p,true,0,true,true)','run<T,A,B>(p,false,pattern,false,true),y=run<T,A,B>(p,true,pattern,true,true)')
    s=s.replace('pair<half,true,false>(1,16,272,1056);return 7;','pair<half,true,false>(1,80,144,1056);return 7;')
    a=s.index('    Mock::need(newA<oldA');s=s[:a]+'''
    pair<half,false,false>(1,128,256,1024);pair<bfloat16_t,true,true>(1,128,256,1024);
    pair<half,false,false>(1,80,144,1056);pair<half,false,true>(1,80,144,1056);
    pair<half,true,false>(1,80,144,1056);pair<half,true,true>(1,80,144,1056);
    pair<bfloat16_t,false,false>(1,80,144,1056);pair<bfloat16_t,false,true>(1,80,144,1056);
    pair<bfloat16_t,true,false>(1,80,144,1056);pair<bfloat16_t,true,true>(1,80,144,1056);
    pair<half,false,true>(1,80,144,1504,1,1,1,1);pair<bfloat16_t,true,false>(1,80,144,1504,1,1,1,2);
    Mock::need(newA==oldA&&newB==oldB&&newMM<oldMM&&newL0B<oldL0B,"structural work claims failed");
    std::cout<<"{\\"source_runs\\":"<<runs<<",\\"bitwise_equal_pairs\\":"<<runs/2<<",\\"old_A_bytes\\":"<<oldA<<",\\"new_A_bytes\\":"<<newA
      <<",\\"old_B_bytes\\":"<<oldB<<",\\"new_B_bytes\\":"<<newB<<",\\"old_MMAD_calls\\":"<<oldMM<<",\\"new_MMAD_calls\\":"<<newMM
      <<",\\"old_L0B_calls\\":"<<oldL0B<<",\\"new_L0B_calls\\":"<<newL0B<<",\\"max_relative_vs_FP64\\":"<<maxRelative
      <<",\\"ring_reads_elements\\":"<<reads<<",\\"ready_publications\\":"<<credits<<",\\"arena_peak_bytes\\":[";
    for(int i=0;i<5;++i){if(i)std::cout<<",";std::cout<<OpStats::peak[i];}std::cout<<"]}\\n";
}catch(const std::exception&e){std::cerr<<e.what()<<std::endl;return 1;}}
'''
    b.write(D/'checks.cpp',s);args=[shutil.which('g++'),'-std=c++20','-O2','-pthread','-fno-fast-math','-ffp-contract=off','-DCHECK_R01','checks.cpp']
    exe=D/'checks.exe';call(args+['-o',str(exe)],'compile');print('r06 CPU compiled',flush=True)
    report=json.loads(call([str(exe)],'run'));print(report,flush=True)
    header=D/'extracted.hpp';good=header.read_text()
    try:
        b.write(header,b.once(good,'f.srcStride=ar;','f.srcStride=mr;'))
        exe=D/'fault.exe';call(args+['-DFAULT','-o',str(exe)],'fault_compile')
        p=subprocess.run([str(exe)],cwd=D,capture_output=True,text=True,timeout=90);b.write(D/'fault.log',p.stdout+p.stderr)
        assert p.returncode==1 and ('numeric result' in p.stderr or 'uninitialized' in p.stderr),(p.returncode,p.stderr)
        report['wrong_full_macro_fixpipe_stride_rejected']=p.stderr.strip()
    finally:b.write(header,good)
    report.update(source_sha256=hashlib.sha256((b.OUT/(b.NAME+'.asc')).read_bytes()).hexdigest(),CANN_compiled=False,NPU_tested=False,scope='actual macro-MMAD producer and unchanged R06 consumer on smaller spatial CPU fixtures; full target K, FP16/BF16 wide-scale deterministic data, negative/zero controls; no hardware timing or Cube precision emulation claim')
    b.write(b.OUT/'v12_r06_cpu_checks.json',json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()

"""R49 epilogue replay with unchanged R43 Cube work and retained R48 path."""
from pathlib import Path
import json,shutil,subprocess,hashlib
import build as b
H=Path(__file__).resolve().parent;ROOT=H.parent;D=H/'cpu_build'
def span(s,a,z,new):return s[:s.index(a)]+new+s[s.index(z,s.index(a)):]
def prepare():
    D.mkdir(exist_ok=True)
    for p in (ROOT/'V11_impl_r47_r48/cpu_build').glob('*.hpp'):shutil.copyfile(p,D/p.name)
    shutil.copyfile(H/'r49_extracted.hpp',D/'r49_extracted.hpp')
    s=(ROOT/'V11_impl_r47_r48/cpu_build/source_checks.cpp').read_text(encoding='utf-8')
    s=s.replace('r47_extracted.hpp','r49_extracted.hpp').replace('bmms47','bmms49').replace('R47','R49')
    s=s.replace('route==47','route==49').replace('(47,','(49,').replace('routeRuns[route-47]','routeRuns[route==49?0:1]')
    s=span(s,'    if(route==49){','    std::vector<float>ws', '''    if(route==49){p=bmms83::MakeNative(B,M,N,K,cores);Mock::need(bmms49::Select(p),"R49 fixture outside guard");
        rb=bmms83::NativeRingBytes(p);pb=bmms83::NativePartialBytes(p);slotElements=4*64*128;}
    if(route==48){Mock::need(bmms48::Eligible(B,M,N,K,cores),"R48 fixture outside guard");
        p=bmms48::MakePlan(B,M,N,K,cores);rb=bmms11d::RingBytes(p);pb=0;slotElements=64*128;}
''')
    s=s.replace('CANDIDATE&&route==48','route==48')
    s=span(s,'            if(CANDIDATE){','        },reverse);', '''            if(route==48){bmms48::Entry<T,TA,TB>((GM_ADDR)a.data(),(GM_ADDR)b.data(),(GM_ADDR)y.data(),(GM_ADDR)ws.data(),nullptr,p);return;}
            if(CANDIDATE){bmms49::Entry<T,TA,TB>((GM_ADDR)a.data(),(GM_ADDR)b.data(),(GM_ADDR)y.data(),(GM_ADDR)ws.data(),(GM_ADDR)part,p);return;}
            bmms25::Entry<T,TA,TB,false>((GM_ADDR)a.data(),(GM_ADDR)b.data(),(GM_ADDR)y.data(),(GM_ADDR)ws.data(),(GM_ADDR)part,p);
''')
    s=span(s,'        if(CANDIDATE&&route==49){','        Mock::need(Traffic::mmads', '')
    s=s.replace('<<",\\\"ready\\\":"<<ring.readyCount','<<",\\\"duplicate_elements\\\":"<<OpStats::duplicateElements<<",\\\"reduce_rows\\\":"<<OpStats::reduceRows<<",\\\"manual_v_mte2\\\":"<<OpStats::manualVToMte2<<",\\\"ready\\\":"<<ring.readyCount')
    s=s.replace('{{272,48,3},{528,64,8},{1056,48,20}}','{{272,48,3},{528,64,8},{1056,48,20},{528,48,2},{784,64,2}}')
    b.write(D/'source_checks.cpp',s)
def call(args,stem):
    p=subprocess.run(args,cwd=D,capture_output=True,text=True,timeout=600)
    b.write(D/(stem+'.stdout.txt'),p.stdout);b.write(D/(stem+'.stderr.txt'),p.stderr)
    if p.returncode:raise RuntimeError(stem+': '+p.stderr[-3000:])
    return p.stdout
def main():
    b.main();prepare()
    args=[shutil.which('g++'),'-std=c++20','-O2','-pthread','-fno-fast-math','-ffp-contract=off','-DCHECK_R01=1','source_checks.cpp']
    runs={}
    for name,mode in [('R48_PARENT',0),('R49',1)]:
        exe=D/(name+'.exe');call(args+['-DCANDIDATE='+str(mode),'-o',str(exe)],name+'_compile');print(name+' compiled',flush=True)
        runs[name]=json.loads(call([str(exe)],name+'_run'));assert runs[name]['strict_misses']==0
        b.write(H/(name+'_CPU_RESULT.json'),json.dumps(runs[name],indent=2)+'\n')
        print(name+': '+json.dumps({k:v for k,v in runs[name].items() if k not in ['fixtures','output_bits']}),flush=True)
    assert runs['R48_PARENT']['output_bits']==runs['R49']['output_bits']
    expected_same=['pM','pN','blocks','mmads','nd2nz','gm_input_bytes','l0_bytes','fixpipes','barriers','partial_bytes','ready','reduce_rows']
    for key,v in runs['R48_PARENT']['fixtures'].items():
        after=runs['R49']['fixtures'][key]
        for metric in expected_same:assert v[metric]==after[metric],(key,metric)
        if key.startswith('48_'):assert v==after
        else:assert after['duplicate_elements']==0 and after['manual_v_mte2']==0
    header=D/'r49_extracted.hpp';good=header.read_text(encoding='utf-8')
    try:
        b.write(header,b.once(good,'uint32_t((TN-p.N)*4),0,0','0,0,0'))
        exe=D/'bad_ring_pitch.exe';call(args+['-DCANDIDATE=1','-DNEGATIVE_PADDING','-o',str(exe)],'bad_pitch_compile')
        p=subprocess.run([str(exe)],cwd=D,capture_output=True,text=True,timeout=45)
        b.write(D/'bad_pitch.log',p.stdout+p.stderr)
        assert p.returncode==1 and ('uninitialized' in p.stderr or 'invalid padding consumed' in p.stderr),p.stderr
        fault=p.stderr.strip()
    finally:b.write(header,good)
    report={'scope':'actual producer/consumer C++ on CPU storage/arithmetic/event adapters; not device execution',
        'source_sha256':hashlib.sha256((b.OUT/(b.NAME+'.asc')).read_bytes()).hexdigest(),
        'all_outputs_bitwise_equal_to_R48_parent_in_model':True,'unchanged_metrics':expected_same,
        'R48_path_work_metrics_unchanged':True,'fault_wrong_ring_pitch_rejected':fault,
        'CANN_compiled':False,'NPU_tested':False,
        'runs':{n:{k:v for k,v in r.items() if k!='output_bits'} for n,r in runs.items()},
        'model_header_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in D.glob('*.hpp')}}
    b.write(b.OUT/'CPU_CHECKS.json',json.dumps(report,indent=2)+'\n');print('R49 source checks and negative control passed.',flush=True)
if __name__=='__main__':main()

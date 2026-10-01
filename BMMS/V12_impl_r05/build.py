from pathlib import Path
import importlib.util,hashlib,json
H=Path(__file__).resolve().parent;ROOT=H.parent;OUT=ROOT/'BMMS_V12'
spec=importlib.util.spec_from_file_location('prev',ROOT/'V12_impl_r04/build.py');prev=importlib.util.module_from_spec(spec);spec.loader.exec_module(prev)
write,once,function,host=prev.write,prev.once,prev.function,prev.host
BASE=OUT/'v12_baseline_r03.asc';SHA=prev.SHA;NAME='v12_r05_probe_r04_coverage'

def changes(raw):
    s=raw.decode();h=host(s,'bmms11r2')
    old='const auto p=MakePlan(B,M,N,K,cores);uint8_t* ws=nullptr;'
    new='''// V12_R05_PROBE_BEGIN: predicate uses the untouched v12_r03 baseline plan.
    const auto observed=MakePlan(B,M,N,K,cores);
    auto p=observed;
    const bool candidateHit=B==1&&M>=1024&&N>=1024&&K>=1024&&K<1536&&
        observed.nTiles/observed.pN>=2;
    // Existing dtype, R06 eligibility and family checks above are retained.
    // Real R06 computation with one group; no cached-A implementation is used.
    if(candidateHit){p.pM=1;p.pN=1;p.tasks=p.B;p.blocks=1;}
    uint8_t* ws=nullptr;
    // V12_R05_PROBE_END'''
    updated=once(h,old,new)
    assert raw.count(h.encode())==1
    return h.encode(),updated.encode()

def main():
    raw=BASE.read_bytes();assert hashlib.sha256(raw).hexdigest()==SHA
    old,new=changes(raw);data=raw.replace(old,new,1)
    assert data.replace(new,old,1)==raw
    assert b'BMMS1204_BEGIN' not in data and b'BMMS1202_BEGIN' not in data
    (OUT/(NAME+'.asc')).write_bytes(data)
    write(OUT/'v12_r05_manifest.json',json.dumps({'file':NAME+'.asc','purpose':'diagnosis only: full r04 dispatch coverage using original R06 one-group stress','parent':BASE.name,'parent_sha256':SHA,'sha256':hashlib.sha256(data).hexdigest(),'single_host_function_changed':True,'device_source_unchanged':True,'r03_recovered_byte_for_byte':True},indent=2)+'\n')
    print('Built '+NAME)
if __name__=='__main__':main()

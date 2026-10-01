"""CPU checks for stage parity, NZ block coverage and source containment.

This models ownership/event ordering; it is not a substitute for device sanitizer.
"""
from pathlib import Path
import hashlib,json,subprocess

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'V12_npu_lab/results/case12_k1_20261001';OUT.mkdir(exist_ok=True)
base=(ROOT/'BMMS_V12/v12_baseline_r41.asc').read_bytes().decode()
report={'kind':'CPU static/model checks, not NPU execution','variants':[]}
for version,k1 in [(51,320),(52,192)]:
    src=(ROOT/f'BMMS_V12/v12_r{version}_case12_kstage{k1}.asc').read_bytes().decode()
    a=src.index(f'// BMMS12{version}_BEGIN');b=src.index(f'// BMMS12{version}_END',a)+len(f'// BMMS12{version}_END\n\n')
    hook=f'    if(bmms12{version}::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
    assert (src[:a]+src[b:]).replace(hook,'',1)==base
    p0=base[base.index('template<class T,bool TA,bool TB>\nclass MacroMmadProducer',base.index('namespace bmms1230 {')):base.index('class RowMaxConsumer {',base.index('namespace bmms1230 {'))]
    assert p0 in src[a:b]
    assert f'K1={k1},K0=64' in src[a:b] and 'bmms1230::RowMaxConsumer op' in src[a:b]
    assert 'if(tb ||' in src[a:b]
    report['variants'].append({'version':version,'sha256':hashlib.sha256(src.encode()).hexdigest(),'parent_recovered_exactly':True,'producer_body_unchanged':True,'consumer_reused':True})

traces=[];coverage_checks=0
for k1 in [192,256,320]:
    chunks=[min(k1,1536-k) for k in range(0,1536,k1)]
    assert 2*(128+256)*k1*2<=512*1024
    for macro_count in range(1,26):
        ready=[None,None];free=[False,False];live=[None,None];start=0;prefetched=False
        def load(slot,macro,stage):
            assert ready[slot] is None and live[slot] is None and not free[slot]
            ready[slot]=live[slot]=(macro,stage)
        def drain(slot):
            assert free[slot];free[slot]=False
        starts=[]
        for macro in range(macro_count):
            starts.append(start);has_next=macro+1<macro_count
            current_start=start
            if not prefetched:load(current_start,macro,0)
            prefetched=False;order=[]
            for ki,kr in enumerate(chunks):
                s=(ki&1)^current_start
                assert ready[s]==live[s]==(macro,ki);ready[s]=None
                if ki+1<len(chunks):
                    nxt=s^1
                    if ki>=1:drain(nxt)
                    load(nxt,macro,ki+1)
                elif has_next:
                    nxt=s^1
                    if len(chunks)>=2:drain(nxt)
                    load(nxt,macro+1,0);start=nxt;prefetched=True
                order.extend(ki*k1+kk for kk in range(0,kr,64))
                assert not free[s];free[s]=True;live[s]=None
            assert order==list(range(0,1536,64))
            if has_next:drain(((len(chunks)-1)&1)^current_start)
            else:
                for s in range(min(2,len(chunks))):drain(s^current_start)
                start=0
        assert ready==live==[None,None] and not any(free)
        traces.append({'K1':k1,'macro_count':macro_count,'starts':starts})
    # Check exact 16x16 blocks loaded from packed L1 for all M/N tails supported by scope.
    for ar in range(16,129,16):
        for br in [64,128,192,256]:
            for ta in [False,True]:
                for kr1 in sorted(set(chunks)):
                    aa=[];bb=[]
                    for kk in range(0,kr1,64):
                        kr0=min(64,kr1-kk)
                        for i in range(ar//16):
                            off=i*kr1*16+kk*16 if ta else (kk//16)*ar*16+i*256
                            aa.extend(off//256+q*(1 if ta else ar//16) for q in range(kr0//16))
                        for j in range(kr0//16):
                            off=(kk+j*16)*16
                            bb.extend(off//256+q*(kr1//16) for q in range(br//16))
                    assert sorted(aa)==list(range(ar*kr1//256))
                    assert sorted(bb)==list(range(br*kr1//256))
                    coverage_checks+=1
prefix=(ROOT/'V12_npu_lab/results/parallel_epilogue_20260929/audit_r48.cpp').read_text().split('namespace bmms11r2 {')[0]
for ns in ['bmms11r2','bmms1230','bmms1241']:
    a=base.index('namespace '+ns+' {');b=base.index('template<class T,bool TA,bool TB>',a)
    prefix+=base[a:b]+'}\n'
src=(ROOT/'BMMS_V12/v12_r51_case12_kstage320.asc').read_text()
a=src.index('namespace bmms1251 {');b=src.index('template<class T,bool TA,bool TB>',a)
prefix+=src[a:b]+'}\n'
code=prefix+r'''
int main(){int active=0,active20=0;
 for(int cores=1;cores<=64;++cores)for(int M=1280;M<1536;M+=16)
 for(int N=4096;N<6144;N+=64)for(int ta=0;ta<2;++ta){
  if(!bmms1251::Eligible(1,M,N,1536,cores)||!bmms1251::AlignedPitch(M,N,1536,ta,false))continue;
  ++active;auto p=bmms1251::MakePlan(1,M,N,1536,cores);
  assert(p.pM==p.mTiles&&p.pN==2&&p.tasks==cores&&p.blocks==cores);
  if(cores==20){assert(M==1280);++active20;}
  assert(!bmms1251::Eligible(1,M,N,1568,cores));
  assert(!bmms1251::Eligible(2,M,N,1536,cores));
  assert(!bmms1251::Eligible(1,1536,N,1536,cores));
  assert(!bmms1251::Eligible(1,M,6144,1536,cores));
 }
 assert(active==640&&active20==64);
 printf("{\"active_metadata_plans_all_cores\":%d,\"active_metadata_plans_20_cores\":%d}\n",active,active20);
}
'''
(OUT/'host_guard.cpp').write_text(code)
subprocess.run(['g++','-O2','-std=c++17',str(OUT/'host_guard.cpp'),'-o',str(OUT/'host_guard.exe')],check=True)
host=json.loads(subprocess.check_output([str(OUT/'host_guard.exe')],text=True))
report.update(host_guard=host,l1_event_traces=len(traces),nz_block_coverage_checks=coverage_checks,K0_order_unchanged=True,
              limitations='Sequential ownership model does not establish physical pipeline race freedom; actual CANN compile and numerical tests required.')
(OUT/'static_audit.json').write_text(json.dumps(report,indent=2)+'\n')
(OUT/'l1_traces.json').write_text(json.dumps(traces,indent=2)+'\n')
print(json.dumps(report,indent=2))

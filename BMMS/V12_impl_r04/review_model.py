"""Independent slot identity / two-pipeline dependency and NZ index audit.

Not a hardware simulator. Model FIFO MTE2/MTE1 queues and explicit event edges;
does not model overlapping instructions within a queue or CANN legality.
"""
from pathlib import Path
import json,hashlib
H=Path(__file__).resolve().parent;OUT=H.parent/'BMMS_V12'

class Audit:
    def __init__(self,mutation=''):
        self.clocks=[[0,0],[0,0]];self.events={};self.slots={};self.mutation=mutation;self.ops=0
    def tick(self,q):
        self.clocks[q][q]+=1;self.ops+=1;return tuple(self.clocks[q])
    def set(self,q,name):
        assert name not in self.events,'event credit overwritten'
        self.events[name]=self.tick(q)
    def wait(self,q,name):
        v=self.events.pop(name)
        if self.mutation=='drop_ready_wait' and name.startswith('ready'):return
        if self.mutation=='drop_free_wait' and name.startswith('free'):return
        self.clocks[q]=[max(a,b) for a,b in zip(self.clocks[q],v)];self.tick(q)
    def write(self,slot,identity):
        now=self.tick(0)
        if slot in self.slots:
            _,_,read=self.slots[slot]
            assert read<=now[1],f'overwrite before MTE1 readers finish: {slot}'
        self.slots[slot]=(identity,now[0],0)
    def read(self,slot,expected):
        now=self.tick(1)
        assert slot in self.slots,f'uninitialized slot {slot}'
        identity,write,_=self.slots[slot]
        assert write<=now[0],f'read before MTE2 write finishes: {slot}'
        assert identity==expected,f'stale cache identity {slot}'
        self.slots[slot]=(identity,write,now[1])
    def macro(self,K,mkey,nkey,ar,br,first):
        stages=(K+255)//256
        def load(ki):
            s=ki%2;k=ki*256;kr=min(256,K-k)
            refresh=first and self.mutation!='never_refresh' and (self.mutation!='keep_first_m' or mkey==(0,0))
            if refresh or k>=512:
                self.write(('A',s+(2 if k<512 else 0)),(mkey,ar,k,kr))
            self.write(('B',s),(nkey,br,k,kr));self.set(0,'ready'+str(s))
        load(0)
        for ki in range(stages):
            s=ki%2;k=ki*256;kr=min(256,K-k);self.wait(1,'ready'+str(s))
            if ki+1<stages:
                if ki>=1:self.wait(0,'free'+str(1-s))
                load(ki+1)
            for kk in range(0,kr,64):
                aSlot=s+(2 if k<512 and self.mutation!='wrong_cache_read' else 0)
                self.read(('A',aSlot),(mkey,ar,k,kr));self.read(('B',s),(nkey,br,k,kr))
            self.set(1,'free'+str(s))
        for s in range(2):self.wait(0,'free'+str(s))
        assert not self.events

def exercise(mutation=''):
    cases=ops=0
    for K in range(1024,1536,32):
        for ar in range(16,129,16):
            for ns in [1,2,3,5]:
                a=Audit(mutation)
                # Reuse cached A, then replace it for a new M and another task.
                for task,m,rows in [(0,0,ar),(0,128,128),(1,256,ar)]:
                    for n in range(ns):a.macro(K,(task,m),(task,n),rows,16 if n==ns-1 else 256,n==0)
                cases+=1;ops+=a.ops
    return cases,ops

def addresses():
    # Build producer ND->NZ positions from logical source coordinates, invert it,
    # then compare the L0 reader formula without using the CPU cube model.
    checked=0
    for K in range(1024,1536,32):
        for ar in range(16,129,16):
            for ta in [False,True]:
                for kBase in range(0,K,256):
                    kr=min(256,K-kBase)
                    pos={}
                    for m in range(ar):
                        for k in range(kr):
                            r,c=(k,m) if ta else (m,k)
                            stride=kr if ta else ar
                            addr=c//16*stride*16+r*16+c%16
                            assert addr not in pos;pos[addr]=(m,kBase+k)
                    for mo in range(0,ar,64):
                        for i in range(min(64,ar-mo)//16):
                            for kk in range(0,kr,64):
                                for block in range(min(64,kr-kk)//16):
                                    off=((mo//16+i)*kr*16+kk*16 if ta else kk//16*ar*16+(mo+i*16)*16)
                                    off+=block*(1 if ta else ar//16)*256
                                    for r in range(16):
                                        for c in range(16):
                                            addr=off+(c*16+r if ta else r*16+c)
                                            assert pos[addr]==(mo+i*16+r,kBase+kk+block*16+c)
                                            checked+=1
    return checked

def main():
    code=(OUT/'v12_r04_case9_10_partial_a_cache.asc').read_text()
    for required in ['K1=256,K0=64,CACHE_K=512','if(firstN||k0>=CACHE_K)','s1+(kBase<CACHE_K?2:0)','n0==nBegin']:
        assert required in code,'source/model premise changed'
    cases,ops=exercise();print('dependency histories',cases,flush=True)
    faults={}
    for mutation in ['drop_ready_wait','drop_free_wait','wrong_cache_read','never_refresh','keep_first_m']:
        try:exercise(mutation)
        except AssertionError as e:faults[mutation]=str(e)
        else:raise AssertionError('fault escaped: '+mutation)
    checked=addresses();print('logical A element address checks',checked,flush=True)
    previous=json.loads((OUT/'v12_r04_cpu_checks.json').read_text())
    total=previous['old_A_bytes']+previous['old_B_bytes'];saved=previous['old_A_bytes']-previous['new_A_bytes']
    result={'source_sha256':hashlib.sha256((OUT/'v12_r04_case9_10_partial_a_cache.asc').read_bytes()).hexdigest(),
      'independent_slot_dependency_histories':cases,'modeled_operations':ops,'logical_A_address_checks':checked,'mutations_rejected':faults,
      'previous_sample_total_AB_bytes':total,'previous_sample_saved_AB_bytes':saved,'previous_sample_total_AB_reduction_fraction':saved/total,
      'scope':'independent manually derived FIFO MTE2/MTE1 partial-order and A NZ address model; not device execution; no proof of hardware asynchronous completion semantics',
      'CANN_compiled':False,'NPU_tested':False}
    (OUT/'v12_r04_review_checks.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()

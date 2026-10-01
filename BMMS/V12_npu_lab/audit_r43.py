from pathlib import Path
import json,hashlib
root=Path(__file__).resolve().parents[1];out=root/'V12_npu_lab/results/wide_pingpong_20260929';out.mkdir(exist_ok=True)
base=(root/'BMMS_V12/v12_baseline_r41.asc').read_text(encoding='utf-8')
src=(root/'BMMS_V12/v12_r43_case8_nz_prefetch.asc').read_text(encoding='utf-8')
def get(s,ns):
    a=s.index('// BMMS'+ns+'_BEGIN');b=s.index('// BMMS'+ns+'_END',a)+len('// BMMS'+ns+'_END');return s[a:b]
old=get(base,'1219');new=get(src,'1243').replace('1243','1219')
assert old[:old.index('class NzProducer')]==new[:new.index('class NzProducer')]
assert old[old.index('class MaskedRowMaxConsumer'):]==new[new.index('class MaskedRowMaxConsumer'):]
tasks=0;macros=0;stages=0
for kcount in range(1,9):
    for lengths in [(1,),(2,),(3,),(4,),(7,),(17,),(1,1),(2,3),(3,1),(8,13,2)]:
        ready=[False]*2;free=[False]*2;start=0;prefetched=False
        def load(slot):
            assert not ready[slot] and not free[slot]
            ready[slot]=True
        def reclaim(slot):
            assert free[slot]
            free[slot]=False
        for length in lengths:
            tasks+=1
            assert not prefetched and start==0 and not any(ready+free)
            for tile in range(length):
                macros+=1;hasNext=tile+1<length;currentStart=start
                if not prefetched:load(currentStart)
                prefetched=False
                for ki in range(kcount):
                    stages+=1;s1=(ki%2)^currentStart
                    assert ready[s1];ready[s1]=False
                    if ki+1<kcount:
                        nxt=s1^1
                        if ki>=1:reclaim(nxt)
                        load(nxt)
                    elif hasNext:
                        nxt=s1^1
                        if kcount>=2:reclaim(nxt)
                        load(nxt);start=nxt;prefetched=True
                    # Last L0 read of this L1 stage posts FREE.
                    assert not free[s1];free[s1]=True
                if hasNext:reclaim(((kcount-1)%2)^currentStart)
                else:
                    for s in range(min(2,kcount)):reclaim(s^currentStart)
                    start=0
            assert not prefetched and not any(ready+free)
result=dict(all_pass=True,pack_host_consumer_byte_identical_after_namespace_normalization=True,task_sequences=tasks,macros=macros,l1_stages=stages,limits='Logical ownership model; not proof of hardware asynchronous timing or sanitizer clearance')
(out/'audit_r43.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))

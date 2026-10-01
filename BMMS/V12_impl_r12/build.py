"""Combine row-parallel epilogue with whole-shard producer where structurally suitable."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1];H=ROOT/'V12_npu_lab/harness'
base=(ROOT/'BMMS_V12/v12_baseline_r03.asc').read_bytes()
sha='1c9e9726aa43fdd177c98c645c69bb7d57721d2f1b07d00dfb614324286a404c'
assert hashlib.sha256(base).hexdigest()==sha
parent=(ROOT/'BMMS_V12/v12_r11_splitk_parallel_merge.asc').read_bytes()
a=parent.index(b'// BMMS1211_BEGIN');z=parent.index(b'// BMMS1211_END',a)+len(b'// BMMS1211_END\n\n')
mod=parent[a:z].decode()
whole=(ROOT/'V12_impl_r10/producer.asc').read_text().replace('class Producer','class WholeShardProducer').replace('f.dstStride=TN;','f.dstStride=p.N;')
anchor='// Each active AIV owns 8 entire rows'
assert mod.count(anchor)==1;mod=mod.replace(anchor,whole+anchor,1)
old='if ASCEND_IS_AIC {Producer<T,TA,TB> op;op.Init(a,b,ws,p,&pipe);op.Process();}'
new='''if ASCEND_IS_AIC {
        // N<=64 permits a complete 512-K shard in L0B; TB benefits from
        // transferring contiguous K rows once. Keep the original staged
        // pipeline for wider non-transposed B, where r10 lost overlap.
        if(p.N<=64||TB){WholeShardProducer<T,TA,TB> op;op.Init(a,b,ws,p,&pipe);op.Process();}
        else{Producer<T,TA,TB> op;op.Init(a,b,ws,p,&pipe);op.Process();}
    }'''
assert mod.count(old)==1;mod=mod.replace(old,new,1).replace('1211','1212')
mod=mod.replace('// Original Split-K producer; independent 8-row merge owners and final M sum.',
                '// Capacity/layout-selected producer with row-parallel K merge; independent from r03.')
fragment=mod.encode();anchor=b'extern "C" void run_kernel(GM_ADDR a,const TensorGroupInfo& ia,'
marker=b'    if(bmms23::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;'
hook=marker.replace(b'bmms23::',b'bmms1212::')+b'\r\n'
data=base.replace(anchor,fragment+anchor,1).replace(marker,hook+marker,1)
assert data.replace(fragment,b'',1).replace(hook,b'',1)==base
target=ROOT/'BMMS_V12/v12_r12_splitk_adaptive_merge.asc';target.write_bytes(data);(H/'r12.asc').write_bytes(data)
e=(H/'event_bench_r11.asc').read_text().replace('1211','1212').replace('"r11"','"r12"');(H/'event_bench_r12.asc').write_text(e)
c=H/'CMakeLists.txt';s=c.read_text()
if 'event_bench_r12' not in s:
 a=s.index('add_executable(event_bench_r11');s+=s[a:].replace('r11','r12');c.write_text(s)
run=(H/'run_split_r11.sh').read_text().replace('r11','r12');(H/'run_split_r12.sh').write_text(run,newline='\n')
report=dict(candidate=target.name,sha256=hashlib.sha256(data).hexdigest(),parent='v12_baseline_r03.asc',parent_sha256=sha,
            original_recovered_byte_for_byte=True,producer_policy='whole-shard if N<=64 or TB; original staged otherwise',
            consumer='r11 row-parallel complete K sum then N max then M sum',
            scope='same narrow Case15 metadata guard; third structural experiment, device validation pending')
(ROOT/'BMMS_V12/v12_r12_manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

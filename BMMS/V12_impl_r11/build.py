"""Independent from r10: original producer, parallel row-owned K merge."""
from pathlib import Path
import hashlib, importlib.util, json
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('r10',ROOT/'V12_impl_r10/build.py');h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)

def main():
 raw=h.BASE.read_bytes();assert hashlib.sha256(raw).hexdigest()==h.SHA
 src=raw.decode().replace('\r\n','\n');mod=h.module(src)
 a=src.index('template<class T,bool TA,bool TB>\nclass Producer',src.index('namespace bmms23 {'))
 z=src.index('// Each batch has one AIV owner:',a)
 producer=src[a:z].replace('f.dstStride=TN;','f.dstStride=p.N;')
 # Fixed reservation and K plan retained. Only compact-N Fixpipe pitch changes.
 ma=mod.index('template<class T,bool TA,bool TB>\nclass Producer');mz=mod.index('// Each batch has one AIV owner:',ma)
 mod=mod[:ma]+producer+mod[mz:]
 a=mod.index('// Each batch has one AIV owner:');z=mod.index('template<class T,bool TA,bool TB>\n__aicore__ inline void Entry',a)
 mod=mod[:a]+(Path(__file__).parent/'consumer.asc').read_text()+mod[z:]
 mod=mod.replace('constexpr int TM=bmms23::TM,TN=bmms23::TN,ROWS=bmms23::ROWS;',
                 'constexpr int TM=bmms23::TM,TN=bmms23::TN,KB=bmms23::KB,ROWS=8;')
 mod=mod.replace('bmms23::WorkspaceBytes(p)','(bmms23::WorkspaceBytes(p)+uint64_t(p.M)*sizeof(float))')
 mod=mod.replace('1210','1211').replace('// Same Split-K plan and merge tree; whole-shard L1, capacity-bounded L0.',
                                        '// Original Split-K producer; independent 8-row merge owners and final M sum.')
 fragment=mod.encode();anchor=b'extern "C" void run_kernel(GM_ADDR a,const TensorGroupInfo& ia,'
 marker=b'    if(bmms23::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;'
 hook=marker.replace(b'bmms23::',b'bmms1211::')+b'\r\n'
 data=raw.replace(anchor,fragment+anchor,1).replace(marker,hook+marker,1)
 assert data.replace(fragment,b'',1).replace(hook,b'',1)==raw
 target=ROOT/'BMMS_V12/v12_r11_splitk_parallel_merge.asc';target.write_bytes(data)
 H=ROOT/'V12_npu_lab/harness';(H/'r11.asc').write_bytes(data)
 e=(H/'event_bench_r10.asc').read_text().replace('1210','1211').replace('"r10"','"r11"')
 e=e.replace('bmms23::WorkspaceBytes(p)','(bmms23::WorkspaceBytes(p)+uint64_t(p.M)*sizeof(float))')
 (H/'event_bench_r11.asc').write_text(e)
 c=H/'CMakeLists.txt';s=c.read_text()
 if 'event_bench_r11' not in s:
  a=s.index('add_executable(event_bench_r10');s+=s[a:].replace('r10','r11');c.write_text(s)
 report=dict(candidate=target.name,sha256=hashlib.sha256(data).hexdigest(),parent=h.BASE.name,parent_sha256=h.SHA,
             original_recovered_byte_for_byte=True,producer_change='Fixpipe destination pitch TN -> N only',
             K_partition_and_reduction_tree_preserved=True,extra_workspace_bytes='M*4 <=256',
             row_owners='M/8, aligned disjoint 32-byte row maxima; all AIVs participate in both barriers')
 (ROOT/'BMMS_V12/v12_r11_manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()

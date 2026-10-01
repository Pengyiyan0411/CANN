"""Audit actual host code, flat ownership, row writers and allocation bounds."""
from pathlib import Path
import subprocess,hashlib,json,sys
root=Path(__file__).resolve().parents[1]
out=root/'V12_npu_lab/results/case12_nmajor_20261001';out.mkdir(exist_ok=True)
base=(root/'BMMS_V12/v12_baseline_r41.asc').read_bytes()
source=(root/'BMMS_V12/v12_r59_case12_nmajor_b_resident.asc').read_bytes()
text=source.decode();start=text.index('// BMMS1259_BEGIN');end=text.index('// BMMS1259_END',start)+len('// BMMS1259_END\n\n')
module=text[start:end]
hook='    if(bmms1259::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
assert text.replace(module,'',1).replace(hook,'',1).encode()==base
assert module.count('BMMS1259_KERNEL(bmms1259_')==4
prefix=(root/'V12_npu_lab/results/case12_k1_20261001/host_r54.cpp').read_text().split('int main(){')[0]
host=module[:module.index('template<class T,bool TA,bool TB>')]+'}\n'
main=r'''
int main(){int states=0,active=0,tiles=0;uint64_t ub=0,ws=0;
for(int cores=1;cores<=64;++cores)for(int M=1280;M<1536;M+=16)for(int N=4096;N<6144;N+=64)for(int ta=0;ta<2;++ta){
  ++states;if(!bmms1259::Eligible(1,M,N,1536,cores)||!bmms1259::AlignedPitch(M,N,1536,ta,false))continue;
  ++active;auto p=bmms1259::MakePlan(1,M,N,1536,cores);
  std::vector<int> seen(p.totalTiles,0),merged(M,0);
  assert(p.totalTiles>=p.blocks);
  for(int g=0;g<p.blocks;++g){
    const int first=g*p.totalTiles/p.blocks,last=(g+1)*p.totalTiles/p.blocks;
    assert(first<last);
    for(int t=first;t<last;++t){
      ++seen[t];++tiles;int m=t%p.mTiles*128,n=t/p.mTiles*128;
      int ar=std::min(128,M-m),br=std::min(128,N-n);assert(ar>0&&ar%16==0&&br>0&&br%16==0);
      for(int sub=0;sub<2;++sub){
        int vr=ar/2;assert(m/2+vr<=M/2);
        assert(sub*vr*128+(vr-1)*128+br<=16384);
      }
      // Every incremental B write and all K0 reads stay in the resident allocation.
      for(int ni=0;ni<br/16;++ni){
        for(int k=0;k<1536;k+=256)assert(ni*1536*16+k*16+256*16<=1536*128);
        for(int k=0;k<1536;k+=64)assert(ni*1536*16+k*16+64*16<=1536*128);
      }
    }
    std::vector<int> writers(M,0);
    for(int sub=0;sub<2;++sub)for(int m=0;m<M;m+=128){int vr=std::min(128,M-m)/2;
      assert((g*M+m+sub*vr)%8==0);assert(m/2+vr<=M/2);
      for(int r=0;r<vr;++r)++writers[m+sub*vr+r];
    }
    for(int x:writers)assert(x==1);
  }
  for(int x:seen)assert(x==1);
  for(int worker=0;worker<2*cores;++worker)for(int m=worker*32;m<M;m+=2*cores*32){
    int count=std::min(32,M-m);assert(count%8==0);
    for(int r=0;r<count;++r)++merged[m+r];
    for(int g=0;g<cores;++g){assert(g*32+count<=cores*32);assert(g*M+m+count<=cores*M);}
  }
  for(int x:merged)assert(x==1);
  assert(bmms1259::RingBytes(p)%32==0&&bmms1259::PartialBytes(p)%32==0);
  ub=std::max(ub,bmms1259::AppUbBytes(p));ws=std::max(ws,bmms1259::WorkspaceBytes(p));
}
printf("{\"states\":%d,\"active\":%d,\"tiles_checked\":%d,\"max_ub_bytes\":%llu,\"max_workspace_bytes\":%llu}\n",states,active,tiles,(unsigned long long)ub,(unsigned long long)ws);
}
'''
cpp=out/'host_r59.cpp';exe=out/'host_r59.exe'
cpp.write_text(prefix+host+main)
subprocess.run(['g++','-O2','-std=c++17',str(cpp),'-o',str(exe)],check=True)
r=json.loads(subprocess.check_output([str(exe)],text=True))
# Re-run the independent whole-NZ vs staged-fill and mathematical-semantic oracle.
sys.path.insert(0,str(root/'V12_npu_lab'))
import design_case12_b_stationary as d
r.update(layout=d.audit_b_layout(),semantics=d.audit_semantics(),
         parent_byte_recovery=True,new_device_entries=4,
         sha256=hashlib.sha256(source).hexdigest(),L1_bytes=524288,
         scope='CPU structural and mathematical checks, not device events or NPU accuracy')
(out/'AUDIT_R59.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r,indent=2))

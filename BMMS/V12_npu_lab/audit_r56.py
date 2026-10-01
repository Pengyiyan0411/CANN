from pathlib import Path
import json,hashlib,subprocess
import numpy as np
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V12';out=root/'V12_npu_lab/results/case12_bnz_20261001'
src=(v/'v12_r56_case12_b_nz_prepack.asc').read_bytes().decode();base=(v/'v12_baseline_r41.asc').read_bytes().decode()
a=src.index('// BMMS1256_BEGIN');b=src.index('// BMMS1256_END',a)+len('// BMMS1256_END\n\n');mod=src[a:b]
hook='    if(bmms1256::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
assert src.replace(mod,'',1).replace(hook,'',1)==base
# Recover the original producer after replacing just the B LoadStage block.
def producer(s,ns):
 a=s.index('template<class T,bool TA,bool TB>\nclass MacroMmadProducer',s.index('namespace '+ns+' {'))
 b=s.index('\n};',a)+len('\n};');return s[a:b]
original=producer(base,'bmms1230');now=producer(src,'bmms1256')
a=original.index('        AscendC::Nd2NzParams qb{};');b=original.index('        AscendC::SetFlag<AscendC::HardEvent::MTE2_MTE1>',a)
c=now.index('        static_assert(!TB,');d=now.index('        AscendC::SetFlag<AscendC::HardEvent::MTE2_MTE1>',c)
assert now[:c]+original[a:b]+now[d:]==original
# All 32 N values: model the emitted block-copy descriptors, raw 16-bit words.
# Verify both complete GM NZ pack and every L1 block against independent ND slices.
K=1536; shapes=0;stages=0
for N in range(4096,6144,64):
 source=np.random.default_rng(N).integers(0,65536,size=(K,N),dtype=np.uint16)
 packed=np.zeros(K*N,dtype=np.uint16);written=np.zeros(K*N,dtype=np.uint8)
 for row0 in range(0,K,128):
  for col0 in range(0,N,128):
   rows=128;cols=min(128,N-col0);x=source[row0:row0+rows,col0:col0+cols].copy().reshape(-1)
   z=np.empty(rows*cols,dtype=np.uint16)
   for c0 in range(0,cols,16):
    z[c0*rows:(c0+16)*rows]=x.reshape(rows,cols)[:,c0:c0+16].reshape(-1)
   off=(col0//16)*K*16+row0*16
   for block in range(cols//16):
    dst=off+block*K*16
    packed[dst:dst+rows*16]=z[block*rows*16:(block+1)*rows*16]
    written[dst:dst+rows*16]+=1
 assert np.all(written==1)
 expected=source.reshape(K,N//16,16).transpose(1,0,2).reshape(-1)
 assert np.array_equal(packed,expected)
 for n0 in range(0,N,256):
  br=min(256,N-n0)
  for k0 in range(0,K,256):
   kr=256;off=(n0//16)*K*16+k0*16
   loaded=np.concatenate([packed[off+i*K*16:off+i*K*16+kr*16] for i in range(br//16)])
   wanted=source[k0:k0+kr,n0:n0+br].reshape(kr,br//16,16).transpose(1,0,2).reshape(-1)
   assert np.array_equal(loaded,wanted);stages+=1
 shapes+=1
prefix=(root/'V12_npu_lab/results/case12_k1_20261001/host_r54.cpp').read_text().split('namespace bmms1253 {')[0]
a=mod.index('namespace bmms1256 {');b=mod.index('// Raw 16-bit transport.',a)
code=prefix+mod[a:b]+'}\n'+r'''
int main(){int tests=0,active=0;uint64_t maxub=0,maxws=0;
for(int cores=1;cores<=64;++cores)for(int M=1280;M<1536;M+=16)for(int N=4096;N<6144;N+=64){
 ++tests;if(!bmms1256::Eligible(1,M,N,1536,cores))continue;++active;
 auto p=bmms1256::MakePlan(1,M,N,1536,cores);
 assert(p.tasks==p.blocks&&p.blocks==cores);
 assert(bmms11r2::WorkspaceBytes(p)%32==0);
 maxub=std::max(maxub,bmms1256::AppUbBytes(p));maxws=std::max(maxws,bmms1256::WorkspaceBytes(p));
 assert(bmms1256::AppUbBytes(p)<=190ULL*1024);
 assert(bmms1256::WorkspaceBytes(p)<=128ULL*1024*1024);
}
printf("{\"compared_plans\":%d,\"eligible_plans\":%d,\"max_app_UB_bytes\":%llu,\"max_workspace_bytes\":%llu}\n",tests,active,(unsigned long long)maxub,(unsigned long long)maxws);
}
'''
(out/'host_r56.cpp').write_text(code)
subprocess.run(['g++','-O2','-std=c++17',str(out/'host_r56.cpp'),'-o',str(out/'host_r56.exe')],check=True)
result=json.loads(subprocess.check_output([str(out/'host_r56.exe')],text=True))
result.update(parent_byte_recovery=True,producer_only_B_load_changed=True,all_N_pack_mappings_checked=shapes,L1_stages_checked=stages,
    mapping_test='Raw uint16 all-bit patterns, complete NZ coverage exactly once; separate actual NPU precision required',source_sha256=hashlib.sha256(src.encode()).hexdigest())
(out/'AUDIT_R56.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

"""Final directed ablation: stage-major resident B in L1, no global packing."""
from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V12';lab=root/'V12_npu_lab/case12_k1_20261001'
old=(v/'v12_r60_case12_nmajor_k128.asc').read_bytes().decode()
a=old.index('// BMMS1260_BEGIN');b=old.index('// BMMS1260_END',a)+len('// BMMS1260_END\n\n')
mod=old[a:b].replace('1260','1261')
lo=mod.index('    __aicore__ inline void LoadB(');hi=mod.index('    __aicore__ inline void LoadStage(',lo)
mod=mod[:lo]+mod[hi:]
mod=mod.replace('if(!STREAM_B)LoadB(0,n0,br);','static_assert(STREAM_B,"Stage-major resident B is filled incrementally");')
mod=mod.replace('qb.dstNzC0Stride=p.K;','qb.dstNzC0Stride=K1;')
mod=mod.replace('// Fill the final full-K NZ position, not a compact K1-stage layout.',
                '// Six compact K1 NZ slabs remain resident and are reused by all M macros in the run.')
mod=mod.replace('b1Buf.template Get<T>()[k0*16]','b1Buf.template Get<T>()[(k0/K1)*K1*BN]')
mod=mod.replace('auto sb=b1Buf.template Get<T>();','auto sb=b1Buf.template Get<T>()[(bk/K1)*K1*BN];')
mod=mod.replace('lb.srcStride=TB?1:p.K/16;','lb.srcStride=TB?1:K1/16;')
mod=mod.replace(':(bk+j*16)*16;',':(bk%K1+j*16)*16;')
assert 'LoadB(' not in mod and 'qb.dstNzC0Stride=p.K' not in mod
src=(old[:a]+mod+old[b:]).replace('if(bmms1260::TryLaunch','if(bmms1261::TryLaunch')
hook='    if(bmms1261::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
assert src.replace(mod,'',1).replace(hook,'',1).encode()==(v/'v12_baseline_r41.asc').read_bytes()
name='v12_r61_case12_stage_resident_b.asc';assert not (v/name).exists()
(v/name).write_bytes(src.encode());(lab/'r61.asc').write_bytes(src.encode())
meta=dict(version='v12_r61',file=name,parent='v12_baseline_r41.asc',experiment_parent='v12_r60_case12_nmajor_k128.asc',
          sha256=hashlib.sha256(src.encode()).hexdigest(),status='pending NPU verification',parent_byte_recovery=True,
          change='Only resident B L1 layout: six compact K1=256 NZ slabs; B stays reused across M; L0B stride 256 instead of1536; K0=128',
          new_device_entries=4,L1_bytes=524288,L0A_bytes=65536,L0B_bytes=65536,L0C_bytes=131072)
(v/'v12_r61_manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
cm=(lab/'CMakeLists.txt').read_text().replace('r59 r60)','r59 r60 r61)')
(lab/'CMakeLists.txt').write_bytes(cm.encode())
script=(lab/'check_r60.sh').read_text().replace('r60','r61').replace('R60','R61')
script=script.replace('echo R61_SCREEN >', '''timeout 180 ./build/bench_r61 cases_r59_extra/all.txt 5 results/r61_extra_precision.jsonl >logs/r61_extra_precision.log 2>&1
echo R61_SCREEN >''')
(lab/'check_r61.sh').write_text(script,encoding='utf-8',newline='\n')
# Independent raw-word oracle of the modified L1 packing and every L0B operand.
import numpy as np
checked=0
for br in range(16,129,16):
 raw=np.random.default_rng(br).integers(0,65536,(1536,br),dtype=np.uint16)
 packed=np.empty(1536*128,dtype=np.uint16);writes=np.zeros(packed.size,dtype=np.uint8)
 for stage in range(6):
  k=stage*256
  for ni in range(br//16):
   off=stage*256*128+ni*256*16
   packed[off:off+256*16]=raw[k:k+256,ni*16:(ni+1)*16].reshape(-1)
   writes[off:off+256*16]+=1
 for k in range(0,1536,128):
  recovered=np.empty((128,br),dtype=np.uint16)
  for ni in range(br//16):
   off=k//256*256*128+ni*256*16+k%256*16
   assert np.all(writes[off:off+128*16]==1)
   recovered[:,ni*16:(ni+1)*16]=packed[off:off+128*16].reshape(128,16)
  assert np.array_equal(recovered,raw[k:k+128]);checked+=1
out=root/'V12_npu_lab/results/case12_nmajor_20261001'
(out/'AUDIT_R61.json').write_text(json.dumps(dict(sha256=meta['sha256'],parent_byte_recovery=True,raw_word_K0_slices=checked,
    layout='[K/256,BN/16,256,16], gaps for br<BN never read',resources_same_as_r60=True),indent=2)+'\n')
print(json.dumps(meta))

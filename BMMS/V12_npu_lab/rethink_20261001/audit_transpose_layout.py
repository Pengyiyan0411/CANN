"""CPU audit of r66 ring-to-UB column ownership, including every legal M tail."""
from pathlib import Path
import json
import numpy as np

rng=np.random.default_rng(1266)
checks=[]
for ar in range(16,129,16):
 for br in range(16,257,16):
  c=rng.standard_normal((ar,br)).astype(np.float32)
  # Poison undefined GM cells: each sub-core must read only real D columns/rows.
  ring=np.full((256,128),np.nan,dtype=np.float32)
  ring[:br,:ar]=c.T
  joined=[];owners=np.zeros(ar,dtype=np.int32)
  vr=ar//2
  for sub in range(2):
   ub=np.full((256,64),-np.inf,dtype=np.float32)
   for i in range(br):
    src=i*128+sub*vr
    assert src+vr<=(i+1)*128
    ub[i,:vr]=ring.reshape(-1)[src:src+vr]
   for span in (128,64,32,16,8,4,2,1):
    ub[:span]=np.maximum(ub[:span],ub[span:2*span])
   joined.append(ub[0,:vr].copy());owners[sub*vr:(sub+1)*vr]+=1
  assert np.all(owners==1)
  assert np.array_equal(np.concatenate(joined),np.max(c,axis=1))
  checks.append(dict(M_tail=ar,N_tail=br,UB_row_pitch=64,GM_D_row_pitch=128))
out=dict(checks=checks,count=len(checks),pass_all=True,
         limitation='CPU layout audit, not device timing or concurrency/memory instrumentation')
p=Path(__file__).resolve().parents[1]/'results/rethink_20261001/R66_LAYOUT_AUDIT.json'
p.write_text(json.dumps(out,indent=2)+'\n')
print(f'{len(checks)} legal tile geometries passed')

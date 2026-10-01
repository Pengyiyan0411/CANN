"""Bound each SSH response to tolerate the forwarding plugin's bulk-transfer failures."""
from pathlib import Path
import subprocess,hashlib,time
root=Path(__file__).resolve().parents[1];out=root/'V12_npu_lab/results/case12_bnz_20261001'
remote='/home/developer/bmms_case12_k1_20261001/results/r56_r58_evidence.tar.gz'
host='devenvc_dj1oz.d997053c687f4661b50959c35a550ee0.atomgit.0'
ssh=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','-o','StrictHostKeyChecking=yes','-o',f'UserKnownHostsFile={root.as_posix()}/V12_npu_lab/env/known_hosts',host]
size=int(subprocess.check_output(ssh+[f'stat -c %s {remote}'],timeout=30))
chunk=128*1024;target=out/'evidence.chunked.tar.gz'
with target.open('wb') as f:
 for i,start in enumerate(range(0,size,chunk)):
  want=min(chunk,size-start)
  for attempt in range(3):
   p=subprocess.run(ssh+[f'dd if={remote} bs={chunk} skip={i} count=1 status=none'],capture_output=True,timeout=30)
   if p.returncode==0 and len(p.stdout)==want:break
   if attempt==2:raise RuntimeError(f'chunk {i}: failed, exit {p.returncode}, length {len(p.stdout)}')
   time.sleep(.3)
  f.write(p.stdout)
  if i%12==0:print(f'download {start+want}/{size}',flush=True)
digest=hashlib.sha256(target.read_bytes()).hexdigest()
assert digest=='6c5e6b9a6b2e0036e3896504a30fe04473b07c593f4018c7844d27b6281244da',digest
target.replace(out/'evidence.tar.gz')
print('ARCHIVE_VERIFIED '+digest,flush=True)

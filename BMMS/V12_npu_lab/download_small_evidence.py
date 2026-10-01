from pathlib import Path
import subprocess,hashlib,concurrent.futures
root=Path(__file__).resolve().parent;out=root/'results/small_20261001';parts=out/'archive_parts';parts.mkdir(exist_ok=True)
host='devenvc_dj1oz.d997053c687f4661b50959c35a550ee0.atomgit.0'
args=['scp','-o','BatchMode=yes','-o','ConnectTimeout=15','-o','StrictHostKeyChecking=yes','-o',f'UserKnownHostsFile={root.as_posix()}/env/known_hosts']
def download(i):
 name=f'part_{i:03d}';p=parts/name
 for _ in range(3):
  r=subprocess.run(args+[f'{host}:/home/developer/bmms_small_20261001/archive_parts/{name}',str(p)],capture_output=True,timeout=60)
  if r.returncode==0:return p
 raise RuntimeError(name+': '+r.stderr.decode(errors='replace'))
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:files=list(pool.map(download,range(36)))
raw=b''.join(p.read_bytes() for p in files);h=hashlib.sha256(raw).hexdigest()
assert len(raw)==9415552 and h=='8139dc0c02e208792cd47084b6e36a61662208ea4ebf8f5d51ee1a9ebc3a4f61',(len(raw),h)
(out/'small_evidence.tar.gz').write_bytes(raw)
print('VERIFIED',len(raw),h)

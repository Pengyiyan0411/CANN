from pathlib import Path
import json,zipfile,hashlib
r=Path(__file__).resolve().parent/'results/c1112_20260928';dest=(r/'evidence').resolve()
with zipfile.ZipFile(r/'c1112_evidence.zip') as z:
 assert z.testzip() is None
 for name in z.namelist():assert (dest/name).resolve().is_relative_to(dest),name
 inv=json.loads(z.read('INVENTORY.json'))
 for item in inv:
  data=z.read(item['path']);assert len(data)==item['size'] and hashlib.sha256(data).hexdigest()==item['sha256'],item['path']
 z.extractall(dest)
print('CRC and SHA256 verified',len(inv),'files')

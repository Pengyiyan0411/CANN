from pathlib import Path
import hashlib,json,zipfile

r=Path(__file__).resolve().parent/'results/case12_20260928'
dest=(r/'evidence').resolve()
with zipfile.ZipFile(r/'case12_evidence.zip') as z:
    assert z.testzip() is None
    for name in z.namelist():
        assert (dest/name).resolve().is_relative_to(dest),name
    inventory=json.loads(z.read('INVENTORY.json'))
    for item in inventory:
        data=z.read(item['path'])
        assert len(data)==item['size']
        assert hashlib.sha256(data).hexdigest()==item['sha256'],item['path']
    z.extractall(dest)
print('CRC and SHA256 verified:',len(inventory),'files')
for key in ['public','c8_control','split_control','other_control']:
    data=json.loads((dest/f'results/c12_r21_{key}_summary.json').read_text())
    print(key)
    for row in data['summary']:
        if key=='public' and row['case'][0] not in [12,13,14,15]:continue
        a=row['baseline_median_us'];b=row['candidate_median_us']
        print(row['case'],round(a,3),round(b,3),'delta_us',round(b-a,3),'delta_percent',round(100*(b/a-1),3))

from pathlib import Path
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1];D=ROOT/'BMMS_V12'
base=(D/'v12_baseline_r03.asc').read_bytes()
assert hashlib.sha256(base).hexdigest()=='1c9e9726aa43fdd177c98c645c69bb7d57721d2f1b07d00dfb614324286a404c'
for v,ns,file in [('r10','1210','v12_r10_splitk_full_shard.asc'),('r11','1211','v12_r11_splitk_parallel_merge.asc'),('r12','1212','v12_r12_splitk_adaptive_merge.asc')]:
    data=(D/file).read_bytes();a=data.index(f'// BMMS{ns}_BEGIN'.encode())
    end=f'// BMMS{ns}_END\n\n'.encode();b=data.index(end,a)+len(end)
    hook=f'    if(bmms{ns}::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\r\n'.encode()
    restored=(data[:a]+data[b:]).replace(hook,b'',1)
    assert restored==base
    manifest=json.loads((D/f'v12_{v}_manifest.json').read_text())
    assert hashlib.sha256(data).hexdigest()==manifest['sha256'] and manifest['NPU_tested']
state=json.loads((D/'MAINLINE.json').read_text());assert state['accepted_sota']=='v12_baseline_r03.asc'
assert 'noise' in next(c['status'] for c in state['candidates'] if c['version']=='v12_r07')
with zipfile.ZipFile(D/'v12_r12_case15_submission.zip') as z:
    assert z.testzip() is None
    assert z.read('v12_r12_splitk_adaptive_merge.asc')==(D/'v12_r12_splitk_adaptive_merge.asc').read_bytes()
    assert z.read('v12_baseline_r03.asc')==base
    assert z.read('SUMMARY.json')==(ROOT/'V12_npu_lab/results/split_20260928/SUMMARY.json').read_bytes()
print('Delivery verified: r03 frozen; source restoration and evidence hashes match; submission archive intact.')

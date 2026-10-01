from pathlib import Path
import hashlib,json
r=Path(__file__).resolve().parents[1];o=r/'BMMS_V12'
raw=(o/'v12_r33_shortk_prefetch_allpitch.asc').read_bytes();base=(o/'v12_baseline_r30.asc').read_bytes()
a=raw.index(b'\n// BMMS1233_BEGIN');b=raw.index(b'// BMMS1233_END',a)+len(b'// BMMS1233_END\n\n')
hook=b'    if(bmms1233::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
assert (raw[:a]+raw[b:]).replace(hook,b'',1)==base
module=raw[a:b].decode();assert 'bmms1230::Entry<T,TA,TB>(a,b,y,ring,part,p)' in module
assert '||!AlignedPitch' not in module
code=(r/'V12_npu_lab/check_r30_host.py').read_text(encoding='utf-8');x=code.index('checks=macros=loads=0');y=code.index('result=dict(',x)
scope={};exec(code[x:y].replace('range(1536,4096,32)','range(1024,1536,32)'),scope)
entry=raw[raw.index(b'extern "C" void run_kernel'):].decode()
assert entry.index('bmms1233::TryLaunch')<entry.index('bmms1230::TryLaunch')<entry.index('bmms11r2::TryLaunch')
max_m=8192;ub=65536+32+256+256+3*max_m*4
assert ub<=192*1024 and max_m//64<=255
result=dict(sha256=hashlib.sha256(raw).hexdigest(),baseline_sha256=hashlib.sha256(base).hexdigest(),parent_byte_recovery=True,delegate_to_exact_r30=True,chains=scope['checks'],macros=scope['macros'],loads=scope['loads'],max_explicit_ub_bytes=ub,notes='Discrete state and source audit; not hardware scheduling proof. Full ordinary/sanitized NPU executions reported separately.')
(r/'V12_npu_lab/results/r33_host.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))

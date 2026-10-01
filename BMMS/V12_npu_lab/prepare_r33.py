from pathlib import Path
import hashlib,json
r=Path(__file__).resolve().parents[1];o=r/'BMMS_V12';h=r/'V12_npu_lab/harness'
base=(o/'v12_baseline_r30.asc').read_bytes()
old=(o/'v12_r32_shortk_macro_prefetch.asc').read_bytes().decode()
a=old.index('// BMMS1232_BEGIN');b=old.index('// BMMS1232_END',a)+len('// BMMS1232_END')
mod=old[a:b].replace('1232','1233')
assert mod.count('||!AlignedPitch(M,N,K,ta,tb)')==1
mod=mod.replace('||!AlignedPitch(M,N,K,ta,tb)','')
payload=('\n'+mod+'\n\n').encode();ix=base.index(b'extern "C" void run_kernel');data=base[:ix]+payload+base[ix:]
hook=b'    if(bmms1233::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
ix=data.index(b'    if(bmms1230::TryLaunch');data=data[:ix]+hook+data[ix:]
assert data.replace(payload,b'',1).replace(hook,b'',1)==base
name='v12_r33_shortk_prefetch_allpitch.asc'
(o/name).write_bytes(data);(h/'r33.asc').write_bytes(data)
meta=dict(version='v12_r33',file=name,sha256=hashlib.sha256(data).hexdigest(),parent='v12_baseline_r30.asc',parent_byte_recovery=True,status='experimental; final validation pending',change='Extend exact r30 macro-prefetch implementation to B1 M/N[1024,8192] K[1024,1536), all physical pitches allowed by original R06 eligibility; preserve original r30 entry unchanged')
(o/'v12_r33_manifest.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
(h/'event_bench_r33.asc').write_text((h/'event_bench_r32.asc').read_text(encoding='utf-8').replace('1232','1233').replace('r32','r33'),encoding='utf-8',newline='\n')
cm=h/'CMakeLists.txt';s=cm.read_text(encoding='utf-8')
if 'add_executable(bench_r33 ' not in s:s+='\n'+s[s.index('add_executable(bench_r32 '):].replace('r32','r33')
cm.write_text(s,encoding='utf-8',newline='\n')
g=(h/'generate_dense_balanced.py').read_text(encoding='utf-8').replace('cases_dense_balanced','cases_shortk_final').replace('shapes=[(1344,3136,1728),(1728,6208,3392)]','shapes=[(2048,1536,1408),(1168,3216,1120),(5120,1280,1216),(1104,4096,1472)]').replace('2092830','2092933')
(h/'generate_shortk_final.py').write_text(g,encoding='utf-8',newline='\n')
v=(h/'validate_dense_next.sh').read_text(encoding='utf-8')
v=v.replace('cmake --build build --target "sanitize_${version}"','cmake -S . -B build >logs/r33_configure.log 2>&1\ncmake --build build --target "${version}_build" "sanitize_${version}"')
v=v.replace('echo SANITIZED_BUILD_DONE','echo SANITIZED_BUILD_DONE\npython3 generate_shortk_final.py >results/shortk_final_generation.log 2>&1\necho FINAL_DATA_DONE')
v=v.replace("'shortk cases_shortk'","'shortk cases_shortk' 'independent cases_shortk_final'")
v=v.replace('cases_shortk/holdout.txt','cases_shortk_final/manifest.txt')
v=v.replace('echo PRECISION_EVENTS_DONE','./build/event_bench_${version} cases_shortk/manifest.txt 6 "results/${version}_all80_event.jsonl" >"results/${version}_all80_event.log" 2>&1\necho PRECISION_EVENTS_DONE')
v=v.replace('cases_shortk/sanitize.txt','cases_shortk/sanitize_final.txt')
v=v.replace(': >"results/${version}_sanitizer_status.txt"','python3 - <<\'PY\'\nfrom pathlib import Path\np=Path("cases_shortk");ids={64,65,72,73}\n(p/"sanitize_final.txt").write_text("".join(x+"\\n" for x in (p/"manifest.txt").read_text().splitlines() if int(x.split()[0]) in ids))\nPY\n: >"results/${version}_sanitizer_status.txt"')
(h/'validate_r33.sh').write_text(v,encoding='utf-8',newline='\n')
print(json.dumps(meta))

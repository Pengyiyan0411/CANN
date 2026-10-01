from pathlib import Path
import hashlib,json
r=Path(__file__).resolve().parents[1];o=r/'BMMS_V12';h=r/'V12_npu_lab/harness'
base=(o/'v12_baseline_r19.asc').read_bytes()
src=(o/'v12_r26_dense_macro_consumer.asc').read_bytes().replace(b'1226',b'1227')
a=src.index(b'// BMMS1227_BEGIN');b=src.index(b'// BMMS1227_END',a)
module=src[a:b];old=b'constexpr int TM=64,TN=128,AM=128,BN=256,K1=256,K0=64,MACRO_ELEMS=4*TM*TN;'
assert module.count(old)==1
module=module.replace(old,old.replace(b'K1=256',b'K1=320'))
src=src[:a]+module+src[b:]
name='v12_r27_dense_kstage320.asc';(o/name).write_bytes(src);(h/'r27.asc').write_bytes(src)
m=dict(version='v12_r27',file=name,sha256=hashlib.sha256(src).hexdigest(),parent='v12_baseline_r19.asc',parent_sha256=hashlib.sha256(base).hexdigest(),
 status='experimental; validation pending',change='r26 structure; K1 256->320, full L1 double buffer retained. L1 491520 bytes; L0 layout/stride and accumulation unchanged.')
(o/'v12_r27_manifest.json').write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8')
(h/'event_bench_r27.asc').write_text((h/'event_bench_r26.asc').read_text(encoding='utf-8').replace('1226','1227'),encoding='utf-8',newline='\n')
cm=h/'CMakeLists.txt';t=cm.read_text(encoding='utf-8')
if 'add_executable(bench_r27 ' not in t:t+='\n'+t[t.index('add_executable(bench_r26 '):].replace('r26','r27')
cm.write_text(t,encoding='utf-8',newline='\n')
(h/'screen_r27.sh').write_text((h/'screen_r26.sh').read_text(encoding='utf-8').replace('r26','r27').replace('R26','R27'),encoding='utf-8',newline='\n')
p=h/'analyze_dense_macro.py';t=p.read_text(encoding='utf-8').replace('for v in [25,26]:','for v in [25,26,27]:');p.write_text(t,encoding='utf-8',newline='\n')
# Arithmetic coverage of every allowed K, including 32-element tails.
for K in range(1536,4096,32):
 consumed=[]
 for k in range(0,K,320):
  length=min(320,K-k)
  for kk in range(0,length,64):consumed.extend(range(k+kk,k+kk+min(64,length-kk)))
 assert consumed==list(range(K))
assert 2*(128+256)*320*2==491520 and 491520<=512*1024
a=src.index(b'\n// BMMS1227_BEGIN');b=src.index(b'// BMMS1227_END',a)+len(b'// BMMS1227_END\n\n')
hook=b'    if(bmms1227::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
assert (src[:a]+src[b:]).replace(hook,b'',1)==base
print(name,m['sha256'])

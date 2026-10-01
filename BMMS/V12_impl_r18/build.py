from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parents[1];H=R/'V12_npu_lab/harness'
raw=(R/'BMMS_V12/v12_baseline_r12.asc').read_bytes();sha=hashlib.sha256(raw).hexdigest()
assert sha=='a845fd9538fe71d5f6284fced34781d8fb7e997105c51065a84b344818ddbd2b'
s=(R/'BMMS_V12/v12_r17_case8_ub_repack_nz.asc').read_text();a=s.index('// BMMS1217_BEGIN');b=s.index('// BMMS1217_END',a)+len('// BMMS1217_END')
mod=s[a:b].replace('1217','1218')
anchor='static inline bool ValidPlan('
policy='''// Measured dispatch policy, not an API validity requirement. Preserve the
// R43 path when the important ND source pitches already align to 128 bytes.
static inline bool PreferNz(const CubePlan& p,bool ta,bool tb){
    return (ta&&(p.M%64)!=0)||(((tb?p.K:p.N)%64)!=0);
}
'''
mod=mod.replace(anchor,policy+anchor,1)
mod=mod.replace('    if(!ValidPlan(p,cores))return false;','    if(!ValidPlan(p,cores)||!PreferNz(p.cube,ta,tb))return false;',1)
frag=(mod+'\n\n').encode();anchor=b'extern "C" void run_kernel(GM_ADDR a,const TensorGroupInfo& ia,'
idx=raw.index(b'    if(bmms_c8p43::TryLaunch');end=raw.index(b'\n',idx)+1;line=raw[idx:end];hook=line.replace(b'bmms_c8p43::',b'bmms1218::')
data=raw.replace(anchor,frag+anchor,1).replace(line,hook+line,1)
assert data.replace(frag,b'',1).replace(hook,b'',1)==raw
name='v12_r18_case8_adaptive_nz.asc';(R/'BMMS_V12'/name).write_bytes(data);(H/'r18.asc').write_bytes(data)
j=dict(candidate=name,parent='v12_baseline_r12.asc',parent_sha256=sha,sha256=hashlib.sha256(data).hexdigest(),parent_recovered_byte_for_byte=True,status='candidate pending validation',dispatch='original Case8 eligible AND ((TA && Mp%64 !=0) || (TB ? Kp : Np)%64 !=0)',pack_tile=[256,128],pack_ub_bytes=131072,macro_and_plan_unchanged=True)
(R/'BMMS_V12/v12_r18_manifest.json').write_text(json.dumps(j,indent=2)+'\n')
e=(H/'event_bench_r17.asc').read_text().replace('1217','1218').replace('"r17"','"r18"')
e=e.replace('    if(candidate){','    if(candidate&&!bmms1218::PreferNz(plan.cube,ta,tb))candidate=false;\n    if(candidate){',1)
e=e.replace('candidate?"r18":"r12"','(candidate&&bmms1218::PreferNz(p.cube,ta,tb))?"bmms1218":"bmms_c8p43"')
(H/'event_bench_r18.asc').write_text(e,newline='\n')
c=H/'CMakeLists.txt';st=c.read_text()
if 'add_executable(event_bench_r18' not in st:
 a=st.index('add_executable(event_bench_r17');st+=st[a:].replace('r17','r18');c.write_text(st,newline='\n')
(H/'validate_c8_r18.sh').write_text((H/'validate_c8_r17.sh').read_text().replace('r17','r18'),newline='\n')
# Freeze a fresh validation set after deciding the policy above. Never tune
# the predicate using its results; reject if it fails to generalize.
g=(H/'generate_followup.py').read_text();a=g.index('specs=[]');b=g.index('manifest=[];records=[]')
g=g[:a]+'''import random
rng=random.Random(180928)
specs=[]
for i in range(40):
    M=rng.randrange(1024,2048);N=rng.randrange(1024,2048);K=rng.randrange(129,160)*8
    # Deliberately cover nearby pitch residues, including preference false.
    if i%5==0:M=(M//64)*64;N=(N//64)*64;K=(K//64)*64+8
    if i%5==1:K=min(1272,(K//64)*64);N=(N//64)*64+1
    if M%16==0 and N%16==0 and K%32==0:N+=1
    specs.append(dict(id=i,label='c8_final_unseen',B=1,M=M,N=N,K=K,dtype=1+(i//4)%2,ta=(i//2)%2,tb=i%2,pattern='random'))
'''+g[b:]
# K>=1024, strict original lower bound. A rounded 1024 is moved to 1088.
g=g.replace('    if M%16==0','    if K<=1024:K=1088\n    if M%16==0')
g=g.replace("default='cases_followup'","default='cases_c8_final'").replace('720928','1830928')
a=g.index('sets={');b=g.index('for name,ids in sets.items():',a);g=g[:a]+"sets={'manifest':range(len(manifest))}\n"+g[b:]
(H/'generate_c8_final.py').write_text(g,newline='\n')
print(json.dumps(j,indent=2))

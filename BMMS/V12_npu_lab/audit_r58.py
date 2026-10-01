from pathlib import Path
import json,hashlib,subprocess
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V12';out=root/'V12_npu_lab/results/case12_bnz_20261001'
s=(v/'v12_r58_probe_case12_nstride_channels.asc').read_bytes().decode();b=(v/'v12_baseline_r41.asc').read_bytes().decode()
a=s.index('// BMMS1258_BEGIN');e=s.index('// BMMS1258_END',a)+len('// BMMS1258_END\n\n');mod=s[a:e]
hook='    if(bmms1258::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
assert s.replace(mod,'',1).replace(hook,'',1)==b and '__global__' not in mod
prefix=(root/'V12_npu_lab/results/case12_k1_20261001/host_r54.cpp').read_text().split('namespace bmms1253 {')[0]
a=mod.index('namespace bmms1258 {');e=mod.index('static inline bool TryLaunch(',a)
code=prefix+mod[a:e]+'}\n'+r'''
int main(){int tested=0,hit=0;uint64_t maxBytes=0;
for(int cores=1;cores<=64;++cores)for(int M=1280;M<1536;M+=16)for(int N=4096;N<6144;N+=64){
 ++tested;if(!bmms1258::Eligible(1,M,N,1536,cores))continue;++hit;
 auto original=bmms1230::MakePlan(1,M,N,1536,cores),p=original;
 int groups=(N%128==0)?1:2;p.pM=groups;p.pN=1;p.tasks=groups;p.blocks=groups;
 assert(groups<=cores&&p.mTiles>=groups);
 assert(bmms11r2::WorkspaceBytes(p)<=bmms11r2::WorkspaceBytes(original));
 maxBytes=std::max(maxBytes,bmms11r2::WorkspaceBytes(p));
 int last=0;for(int group=0;group<groups;++group){
   int start=group*p.mTiles/groups*128,end=std::min(M,(group+1)*p.mTiles/groups*128);
   assert(start==last&&end>start&&start%16==0&&end%16==0);last=end;
 }assert(last==M);
}
printf("{\"tested_plans\":%d,\"eligible_plans\":%d,\"max_stress_workspace\":%llu}\n",tested,hit,(unsigned long long)maxBytes);
}
'''
(out/'host_r58.cpp').write_text(code);subprocess.run(['g++','-O2','-std=c++17',str(out/'host_r58.cpp'),'-o',str(out/'host_r58.exe')],check=True)
r=json.loads(subprocess.check_output([str(out/'host_r58.exe')],text=True));r.update(parent_byte_recovery=True,new_device_entries=0,source_sha256=hashlib.sha256(s.encode()).hexdigest())
(out/'AUDIT_R58.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
specs=json.loads((root/'V12_npu_lab/results/case12_k1_20261001/evidence/cases/specs.json').read_text())
items=','.join('{'+','.join(str(x[k]) for k in ['id','B','M','N','K','dtype','ta','tb'])+'}' for x in specs)
labels=prefix+mod[a:e]+'}\nint main(){int rows[][8]={'+items+r'''};
for(auto &x:rows){int id=x[0],B=x[1],M=x[2],N=x[3],K=x[4],dt=x[5],ta=x[6],tb=x[7];
 bool hit=!tb&&(dt==1||dt==2)&&bmms1258::Eligible(B,M,N,K,20)&&bmms1258::AlignedPitch(M,N,K,ta,tb);
 // Eligible forces K1536, hence neither UseTiny nor UseResident can hold.
 int groups=hit?(N%128==0?1:2):0;
 printf("{\"case\":%d,\"groups\":%d}\n",id,groups);
}}
'''
(out/'labels_r58.cpp').write_text(labels)
subprocess.run(['g++','-O2','-std=c++17',str(out/'labels_r58.cpp'),'-o',str(out/'labels_r58.exe')],check=True)
label_rows=[json.loads(x) for x in subprocess.check_output([str(out/'labels_r58.exe')],text=True).splitlines()]
(out/'LABELS_R58.json').write_text(json.dumps(label_rows,indent=2)+'\n')
print(json.dumps(dict(label_counts={str(i):sum(x['groups']==i for x in label_rows) for i in range(3)})))

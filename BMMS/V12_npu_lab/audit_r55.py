from pathlib import Path
import hashlib, json, subprocess

root=Path(__file__).resolve().parents[1];v=root/'BMMS_V12'
out=root/'V12_npu_lab/results/r55_coverage_20261001'
base=(v/'v12_baseline_r41.asc').read_bytes().decode()
candidate=(v/'v12_r54_case12_stride_gated_m256.asc').read_bytes().decode()
src=(v/'v12_r55_probe_r54_full_gate.asc').read_bytes().decode()
a=src.index('// BMMS1255_BEGIN');b=src.index('// BMMS1255_END',a)+len('// BMMS1255_END\n\n');mod=src[a:b]
hook='    if(bmms1255::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
assert src.replace(mod,'',1).replace(hook,'',1)==base
a=candidate.index('namespace bmms1254 {');b=candidate.index('template<class T,bool TA,bool TB>',a)
candidate_host=candidate[a:b]
a=mod.index('namespace bmms1255 {');b=mod.index('static inline bool TryLaunch(',a)
probe_host=mod[a:b]
assert probe_host.replace('1255','1254')==candidate_host
a=candidate.index('static inline bool TryLaunch(',candidate.index('#undef BMMS1254_KERNEL'))
b=candidate.index('    const auto p=MakePlan(',a)
assert candidate[a:b] in mod
assert src.count('__global__')==base.count('__global__')
prefix=(root/'V12_npu_lab/results/case12_k1_20261001/host_r54.cpp').read_text().split('int main(){')[0]
cpp=prefix+probe_host+'}\n'+r'''
int main(){int n=0,hit=0;uint64_t maxStress=0,minIntended=~uint64_t(0);
for(int cores=1;cores<=64;++cores)for(int M=1280;M<1536;M+=16)
for(int N=4096;N<6144;N+=64){
 ++n;bool a=bmms1254::Eligible(1,M,N,1536,cores),b=bmms1255::Eligible(1,M,N,1536,cores);assert(a==b);
 if(!b)continue;++hit;
 auto intended=bmms1255::MakePlan(1,M,N,1536,cores);
 auto stress=bmms1230::MakePlan(1,M,N,1536,cores);
 stress.pM=1;stress.pN=1;stress.tasks=1;stress.blocks=1;
 const auto large=bmms11r2::WorkspaceBytes(intended),small=bmms11r2::WorkspaceBytes(stress);
 assert(small<=large);assert(stress.mTiles==(M+127)/128&&stress.nTiles==(N+255)/256);
 assert(bmms11r2::RingBytes(stress)%32==0);
 maxStress=std::max(maxStress,small);minIntended=std::min(minIntended,large);
}
printf("{\"compared_plans\":%d,\"eligible_plans\":%d,\"max_stress_workspace\":%llu,\"min_allocated_workspace\":%llu}\n",n,hit,(unsigned long long)maxStress,(unsigned long long)minIntended);
}
'''
(out/'host_audit.cpp').write_text(cpp)
subprocess.run(['g++','-O2','-std=c++17',str(out/'host_audit.cpp'),'-o',str(out/'host_audit.exe')],check=True)
result=json.loads(subprocess.check_output([str(out/'host_audit.exe')],text=True))
result.update(parent_recovered_byte_for_byte=True,eligibility_and_plan_equal_to_r54=True,
              trylaunch_preallocation_guard_copied_exactly=True,new_device_entries=0,
              source_sha256=hashlib.sha256(src.encode()).hexdigest())
(out/'AUDIT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

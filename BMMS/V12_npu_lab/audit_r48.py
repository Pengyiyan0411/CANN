from pathlib import Path
import subprocess,json
r=Path(__file__).resolve().parents[1];o=r/'V12_npu_lab/results/parallel_epilogue_20260929';lab=r/'V12_npu_lab/narrow_dense'
old=(r/'V12_npu_lab/results/b_resident_20260929/audit_r47.cpp').read_text(encoding='utf-8');prefix=old.split('namespace bmms1247 {')[0]
s=(r/'BMMS_V12/v12_r48_case12_parallel_epilogue.asc').read_text(encoding='utf-8');a=s.index('namespace bmms1248 {');b=s.index('class RowMaxConsumer',a)
prefix+=s[a:b]+'}\n'
body=r'''
int main(){long long configs=0,active=0,rows=0,reads=0;size_t maxub=0;
for(int cores:{2,4,8,16,20,24,32,64})for(int M=1280;M<1536;M+=16)for(int N=4096;N<6144;N+=16){
++configs;if(!bmms1248::Eligible(1,M,N,1536,cores))continue;++active;auto p=bmms1248::MakePlan(1,M,N,1536,cores);
std::vector<int> initial(p.pN*M,0),finalRows(M,0);
for(int group=0;group<p.blocks;++group)for(int task=group;task<p.tasks;task+=p.blocks){
int ms=task/p.pN,ns=task%p.pN,m0=ms*p.mTiles/p.pM*128,m1=std::min((ms+1)*p.mTiles/p.pM*128,M);
for(int m=m0;m<m1;++m)++initial[ns*M+m];}
for(int x:initial)assert(x==1);
for(int worker=0;worker<2*p.blocks;++worker)for(int m=worker*64;m<M;m+=2*p.blocks*64){
int vr=std::min(64,M-m);assert(vr%8==0&&vr>0);assert((64-vr)%8==0);
for(int ns=0;ns<p.pN;++ns){int gm=ns*M+m,ub=ns*64;assert(gm+vr<=p.pN*M&&ub+vr<=p.pN*64);reads+=vr;}
for(int j=m;j<m+vr;++j){++finalRows[j];++rows;}}
for(int x:finalRows)assert(x==1);
assert(bmms1248::WorkspaceBytes(p)==bmms11r2::RingBytes(p)+uint64_t(p.pN)*M*4+uint64_t(M)*4);
assert(p.pN<=255);
size_t ub=65536+32+2*256+p.pN*64*4+256+2*M*4;maxub=std::max(maxub,ub);assert(ub<192*1024);
}
printf("{\"configurations\":%lld,\"active\":%lld,\"rows_written\":%lld,\"partial_elements_read\":%lld,\"max_explicit_ub_bytes\":%zu,\"all_pass\":true}\n",configs,active,rows,reads,maxub);
}
'''
(o/'audit_r48.cpp').write_text(prefix+body,encoding='utf-8')
subprocess.run(['g++','-O2','-std=c++17',str(o/'audit_r48.cpp'),'-o',str(o/'audit_r48.exe')],check=True)
out=subprocess.check_output([str(o/'audit_r48.exe')],text=True);json.loads(out);(o/'audit_r48.json').write_text(out);print(out)
code=prefix+r'''int main(){for(int M=1280;M<1536;M+=16)for(int N=4096;N<6144;N+=16)if(bmms1248::Eligible(1,M,N,1536,20)){auto p=bmms1248::MakePlan(1,M,N,1536,20);printf("%d %d %d\n",M,N,p.pN);}}'''
(o/'r48_candidates.cpp').write_text(code,encoding='utf-8');subprocess.run(['g++','-O2','-std=c++17',str(o/'r48_candidates.cpp'),'-o',str(o/'r48_candidates.exe')],check=True)
(lab/'r48_candidates.txt').write_bytes(subprocess.check_output([str(o/'r48_candidates.exe')]))

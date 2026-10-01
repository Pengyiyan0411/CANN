from pathlib import Path
import json,subprocess
r=Path(__file__).resolve().parents[1];o=r/'V12_npu_lab/results/parallel_epilogue_20260929';lab=r/'V12_npu_lab/narrow_dense'
prefix=(o/'audit_r48.cpp').read_text().split('namespace bmms1248 {')[0]
s=(r/'BMMS_V12/v12_r50_case12_deferred_partials.asc').read_text(encoding='utf-8');a=s.index('namespace bmms1250 {');b=s.index('class RowMaxConsumer',a)
prefix+=s[a:b]+'}\n'
code=prefix+r'''
int main(){long long count=0,active=0,writes=0;size_t maxub=0;
for(int cores:{2,4,8,16,20,24,32,64})for(int M=1280;M<1536;M+=16)for(int N=4096;N<6144;N+=16){
++count;if(!bmms1250::Eligible(1,M,N,1536,cores))continue;++active;auto p=bmms1250::MakePlan(1,M,N,1536,cores);
assert(p.pM==1&&p.pN==p.blocks&&p.tasks==p.blocks);
std::vector<int> seen(p.pN*M,0);
for(int ns=0;ns<p.pN;++ns)for(int sub=0;sub<2;++sub){
std::vector<int> ub(M/2,0);for(int m=0;m<M;m+=128){int ar=std::min(128,M-m),vr=ar/2;for(int j=0;j<vr;++j)++ub[m/2+j];}
for(int x:ub)assert(x==1);
int full=M/128,tail=M%128;for(int block=0;block<full;++block)for(int j=0;j<64;++j){
int src=block*64+j,dst=ns*M+sub*64+block*128+j;assert(src<M/2&&dst<(ns+1)*M);++seen[dst];++writes;}
if(tail)for(int j=0;j<tail/2;++j){int src=full*64+j,dst=ns*M+full*128+sub*(tail/2)+j;assert(src<M/2&&dst<(ns+1)*M);++seen[dst];++writes;}
}for(int x:seen)assert(x==1);
size_t ub=65536+32+256+size_t(M/2)*4+3*size_t(M)*4;maxub=std::max(maxub,ub);assert(ub<192*1024);
}
printf("{\"configurations\":%lld,\"active\":%lld,\"partial_elements_written\":%lld,\"max_explicit_ub_bytes\":%zu,\"all_pass\":true}\n",count,active,writes,maxub);
}
'''
(o/'audit_r50.cpp').write_text(code);subprocess.run(['g++','-O2','-std=c++17',str(o/'audit_r50.cpp'),'-o',str(o/'audit_r50.exe')],check=True)
z=subprocess.check_output([str(o/'audit_r50.exe')],text=True);json.loads(z);(o/'audit_r50.json').write_text(z);print(z)
code=prefix+r'''int main(){for(int M=1280;M<1536;M+=16)for(int N=4096;N<6144;N+=16)if(bmms1250::Eligible(1,M,N,1536,20))printf("%d %d\n",M,N);}'''
(o/'r50_candidates.cpp').write_text(code);subprocess.run(['g++','-O2','-std=c++17',str(o/'r50_candidates.cpp'),'-o',str(o/'r50_candidates.exe')],check=True)
(lab/'r50_candidates.txt').write_bytes(subprocess.check_output([str(o/'r50_candidates.exe')]))
# Make independent holdout/special input generator before viewing r50 performance.
gen=(lab/'generate_r47.py').read_text()
gen=gen.replace('290947','290950').replace('r47_candidates','r50_candidates').replace("'r41_holdout']","'r41_holdout','r47_all','r48_holdout']").replace('400+len(specs)','600+len(specs)')
gen=gen.replace('[(1280,5344,1600,1,1),(1520,4800,1632,0,0)]','[(1392,5120,1600,0,0),(1408,5040,1600,1,1)]')
gen=gen.replace("f'r47_{split}.txt'","f'r50_{split}.txt'").replace("'r47_all.jsonl'","'r50_all.jsonl'")
(lab/'generate_r50.py').write_bytes(gen.encode())

from pathlib import Path
import build as b
H=Path(__file__).resolve().parent
s=(b.ROOT/'V11_impl_r50/host_checks.cpp.in').read_text(encoding='utf-8')
s=s.replace('case5=0','case2=0,case5=0')
s=b.once(s,'hit=B==1&&','hit=B>1&&B<=64&&')
s=b.once(s,'want.blocks=1;want.strategy=50;', 'want.blocks=std::min(B,2*((cores>0&&cores<=64)?cores:1));want.strategy=51;')
s=b.once(s,'want.plan={1,M,N,K,kp,tiny,0,0,0,1};','want.plan={B,M,N,K,kp,tiny,want.blocks,0,0,1};')
s=b.once(s,'if(B>1&&M<=32&&N<=32&&K==128)', 'if(B>1&&M>=16&&M<=32&&N>=32&&N<=64&&K==128)')
s=b.once(s,'if(parent.strategy==48)', 'if(parent.strategy==50){need(got==parent,"R50 Case2 changed");++case2;}\n    if(parent.strategy==48)')
s=b.once(s,'case5&&case7&&case13','case2&&case5&&case7&&case13')
s=b.once(s,'for(int B:{1,2})for(int dt:', 'for(int B:{1,2,3,41,64})for(int dt:')
s=b.once(s,'<<",\\\"Case5_metadata_checks\\\":"<<case5', '<<",\\\"R50_Case2_checks\\\":"<<case2<<",\\\"Case5_metadata_checks\\\":"<<case5')
b.write(H/'host_checks.cpp.in',s)

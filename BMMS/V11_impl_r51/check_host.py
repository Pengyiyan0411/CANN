"""Reuse R50's full dispatcher harness, changing only new-target expectations."""
from pathlib import Path
import build as b
H=Path(__file__).resolve().parent
s=(b.ROOT/'V11_impl_r50/check_host.py').read_text(encoding='utf-8')
s=s.replace("ROOT/'V11_impl_r49/host_build/host.cpp'","ROOT/'V11_impl_r50/host_build/host.cpp'")
s=b.once(s,"    s+='namespace bmms71 {\\n'+b.function(base,'static inline int32_t Pow2Up(')+'\\n}\\n'\n",'')
s=s.replace("// Batch the independent row work","// R50 row staging").replace('BMMS50','BMMS51').replace('bmms50','bmms51')
s=b.once(s,"p.M,p.N,p.K,p.kp,p.tiny,0,0,0,1","p.M,p.N,p.K,p.kp,p.tiny,p.workers,0,0,1")
s=b.once(s,'actual.plan={{1,','actual.plan={{p.B,')
s=b.once(s,'actual.strategy=50','actual.strategy=51')
s=b.once(s,"'bmms48','bmms49']","'bmms48','bmms49','bmms50']")
exec(compile(s,str(H/'generated_check_host.py'),'exec'),{'__name__':'__main__','__file__':str(H/'generated_check_host.py')})

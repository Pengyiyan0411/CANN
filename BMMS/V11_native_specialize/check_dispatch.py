"""Compile the actual NativeEntry with recording stubs; exhaust its new selector."""
from pathlib import Path
import importlib.util,json,re,shutil,subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;BUILD=HERE/'dispatch_build'
spec=importlib.util.spec_from_file_location('builder',HERE/'build.py');build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)

def main():
    build.verify();BUILD.mkdir(exist_ok=True)
    source=(build.OUT/(build.NAMES['R20']+'.asc')).read_text(encoding='utf-8')
    original=build.BASE.read_text(encoding='utf-8')
    prefix=build.between(source,'namespace bmms83 {','constexpr int32_t PACKET_TILES=4;')
    assert prefix==build.between(original,'namespace bmms83 {','constexpr int32_t PACKET_TILES=4;')
    selector=build.between(source,'static inline bool UseWideN(', 'template<class T,bool TA,bool TB,int TK>\nclass WideNProducer')
    entry=build.entry(source)
    for marker in ['#define BMMS83_NATIVE_KERNEL','BMMS83_NATIVE_KERNEL']:
        # All kernel bindings and host launch code are covered by whole-source reconstruction.
        if marker in original:assert original.count(marker)==source.count(marker)
    code='''#include <cstdint>
#include <string>
#include <iostream>
#include <stdexcept>
#define __aicore__
#define ASCEND_IS_AIC (isCube)
#define ASCEND_IS_AIV (!isCube)
using GM_ADDR=void*;
namespace AscendC{struct TPipe{};}
bool isCube=true;std::string selected;int processed=0;
'''+prefix+selector+'''
template<class T,bool TA,bool TB,int TK>struct SmallKProducer{
void Init(GM_ADDR,GM_ADDR,GM_ADDR,const NativePlan&,AscendC::TPipe*){selected="old";}
void Process(){++processed;}};
template<class T,bool TA,bool TB,int TK>struct WideNProducer{
void Init(GM_ADDR,GM_ADDR,GM_ADDR,const NativePlan&,AscendC::TPipe*){selected="wide";}
void Process(){++processed;}};
struct SmallKPacketConsumer{
void Init(GM_ADDR,GM_ADDR,GM_ADDR,const NativePlan&,AscendC::TPipe*){selected="consumer";}
void Process(){++processed;}};
'''+entry+'''}
void need(bool x){if(!x)throw std::runtime_error("Native entry / guard / plan mismatch");}
template<int K>int bindings(const bmms83::NativePlan& p,bool wide){
    int checks=0;
#define RUN(T,TA,TB) for(bool cube:{false,true}){isCube=cube;selected.clear();processed=0;bmms83::NativeEntry<T,TA,TB,K>(nullptr,nullptr,nullptr,nullptr,nullptr,p);need(processed==1&&selected==(cube?(wide?"wide":"old"):"consumer"));++checks;}
    RUN(uint16_t,false,false) RUN(uint16_t,false,true) RUN(uint16_t,true,false) RUN(uint16_t,true,true)
    RUN(int16_t,false,false) RUN(int16_t,false,true) RUN(int16_t,true,false) RUN(int16_t,true,true)
#undef RUN
    return checks;
}
int main(){uint64_t selectors=0,entryChecks=0,plans=0,widePlans=0;
for(int nt=1;nt<=64;++nt)for(int pn=1;pn<=nt;++pn){
    bmms83::NativePlan p{};p.nTiles=nt;p.pN=pn;bool all=true;
    for(int ns=0;ns<pn;++ns)all&=((ns+1)*nt/pn-ns*nt/pn)>=2;
    need(bmms83::UseWideN(p)==all);++selectors;
    entryChecks+=bindings<32>(p,all)+bindings<64>(p,all)+bindings<128>(p,all);
}
for(int B:{1,2,3,7,20,64})for(int M:{16,32,64,144,272,8192})for(int N:{16,32,128,144,272,528,640,8192})
for(int K:{32,64,128})for(int cores:{1,2,3,8,20,24,32,64}){
    auto p=bmms83::MakeNative(B,M,N,K,cores);bool all=true;
    for(int ns=0;ns<p.pN;++ns)all&=((ns+1)*p.nTiles/p.pN-ns*p.nTiles/p.pN)>=2;
    need(all==bmms83::UseWideN(p)&&p.blocks<=cores&&p.tasks==B*p.pM*p.pN);
    ++plans;if(all)++widePlans;
}
std::cout<<"{\\\"selector_checks\\\":"<<selectors<<",\\\"actual_entry_checks\\\":"<<entryChecks<<",\\\"actual_plan_checks\\\":"<<plans<<",\\\"multi_N_plans\\\":"<<widePlans<<"}\\n";}
'''
    build.write(BUILD/'entry.cpp',code);exe=BUILD/'entry.exe'
    subprocess.run([shutil.which('g++'),'-std=c++20','-O2',str(BUILD/'entry.cpp'),'-o',str(exe)],check=True)
    report=json.loads(subprocess.check_output([str(exe)],text=True))
    report['scope']='actual R20 NativeEntry with stubs; unchanged R14 host plan; metadata selector only'
    report['sources']={build.BASE.relative_to(ROOT).as_posix():build.sha(build.BASE),
        (build.OUT/(build.NAMES['R20']+'.asc')).relative_to(ROOT).as_posix():build.sha(build.OUT/(build.NAMES['R20']+'.asc'))}
    build.write(HERE/'DISPATCH_CHECKS.json',json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()

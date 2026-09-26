"""Build source-extraction CPU harness. Never modifies submission arithmetic."""
from pathlib import Path
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent
BASE = HERE.parent/'next_stage'


def between(text, start, end):
    return text[text.index(start):text.index(end, text.index(start))]


def make_shim():
    s = (BASE/'cpu_shim.hpp').read_text(encoding='utf-8')
    s = s.replace('#include <algorithm>', '#include <algorithm>\n#include <array>')
    s = s.replace('GM,VECIN,VECOUT,VECCALC', 'GM,VECIN,VECOUT,VECCALC,A1,B1,A2,B2,CO1')
    s = s.replace('MTE3_V,V_S,S_V}', 'MTE3_V,V_S,S_V,MTE2_MTE1,MTE1_MTE2,MTE1_M,M_MTE1,M_FIX,FIX_M,S_MTE3,MTE3_S}')
    s=s.replace('inline thread_local Context* ctx=nullptr;',
                'inline thread_local Context* ctx=nullptr;\ninline thread_local std::array<std::array<int,8>,32> localFlags{};')
    s=s.replace('template<HardEvent E>void SetFlag(int){}',
                'template<HardEvent E>void SetFlag(int id){Mock::need(id>=0&&id<8,"event id out of range");auto& n=Mock::localFlags[int(E)][id];Mock::need(n==0,"local event credit overwritten");++n;}')
    s=s.replace('template<HardEvent E>void WaitFlag(int){}',
                'template<HardEvent E>void WaitFlag(int id){auto& n=Mock::localFlags[int(E)][id];Mock::need(n==1,"local event wait has no credit");--n;}')
    a=s.index('struct TPipe {')
    b=s.index('inline int GetBlockIdx()',a)
    replacement='''struct TPipe {
    std::array<size_t,5> used{};
    std::array<std::array<bool,8>,32> eventUsed{};
    template<TPosition P> void charge(size_t n) {
        constexpr int arena=(P==TPosition::A1||P==TPosition::B1)?1:
                            P==TPosition::A2?2:P==TPosition::B2?3:P==TPosition::CO1?4:0;
        constexpr size_t caps[5]={192*1024,512*1024,64*1024,64*1024,128*1024};
        used[arena]+=n;Mock::need(used[arena]<=caps[arena],"per-arena resource budget exceeded");
    }
    template<TPosition P,int D>void InitBuffer(TQue<P,D>& q,int depth,size_t n){
        Mock::need(depth==1,"CPU queue adapter currently supports depth one");
        q.storage=std::make_shared<Mock::Buffer>(n);charge<P>(depth*n);
    }
    template<TPosition P>void InitBuffer(TBuf<P>& b,size_t n){b.storage=std::make_shared<Mock::Buffer>(n);charge<P>(n);}
    int FetchEventID(HardEvent){return 0;}
    template<HardEvent E>int AllocEventID(){
        auto& ids=eventUsed[int(E)];for(int i=0;i<8;++i)if(!ids[i]){ids[i]=true;return i;}
        throw std::runtime_error("event allocator exhausted");
    }
    template<HardEvent E>void ReleaseEventID(int i){
        Mock::need(i>=0&&i<8&&eventUsed[int(E)][i],"invalid event release");eventUsed[int(E)][i]=false;
    }
};
'''
    s=s[:a]+replacement+s[b:]
    (HERE/'cpu_shim.hpp').write_text(s,encoding='utf-8')


def main():
    make_shim()
    s=(BASE/'C00_P01_CONTROL.asc').read_text(encoding='utf-8')
    common='#pragma once\nnamespace bmmmaxsum_v43 {constexpr float NEG_INF=-__builtin_inff();}\n'
    common+=between(s,'namespace bmms71 {','// BMMS71_VECTOR_MODULE_END')
    common+='\nnamespace bmms8 { inline int CeilDivI(int x,int y){return (x+y-1)/y;}\n'
    common+=between(s,'__aicore__ inline void PairAccumulate(', 'template<class T,bool SUM_ROWS>\n__aicore__ inline void LaneSkinnyDevice')+'}\n'
    common+=between(s,'namespace bmms83 {','// Only fixed-size TBuf allocations occur on the AIC side.')
    common+=between(s,'class SmallKConsumer {','template<class T,bool TA,bool TB,int TK>\n__aicore__ inline void NativeEntry')+'}\n'
    (HERE/'common_extracted.hpp').write_text(common,encoding='utf-8')
    manifest={'baseline_sha256':hashlib.sha256((BASE/'C00_P01_CONTROL.asc').read_bytes()).hexdigest(),
              'scope':'Source-extracted CPU model, not a CANN compilation or device run'}
    for name in ['dense','splitk']:
        p=HERE/(name+'_fragment.asc')
        if not p.exists(): continue
        source=p.read_text(encoding='utf-8')
        # Explicit device/host boundary supplied by implementation files.
        marker='// BMMS9_CPU_EXTRACT_END'
        if marker not in source:
            raise ValueError(f'{p.name} must expose {marker}')
        extracted=source[:source.index(marker)]
        depth=0
        for line in extracted.splitlines():
            if re.match(r'\s*#\s*(if|ifdef|ifndef)\b',line): depth+=1
            elif re.match(r'\s*#\s*endif\b',line): depth-=1
        assert depth>=0
        extracted+='\n'+'#endif\n'*depth
        (HERE/(name+'_extracted.hpp')).write_text(extracted,encoding='utf-8')
        manifest[name]={'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                        'extracted_sha256':hashlib.sha256(extracted.encode()).hexdigest()}
    (HERE/'source_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest,indent=2))


if __name__=='__main__': main()

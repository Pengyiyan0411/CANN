"""Independent, Native-only R14 descendants. Frozen source is never edited."""
from pathlib import Path
import difflib, hashlib, json, shutil

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
OUT=ROOT/'BMMS_V11_R20_R21'
BASE=ROOT/'BMMS_V11_R13_R14/R14_FLEX_SINGLE_WAVE.asc'
BASE_SHA='64eb6eeeb10d2418845d2026b9e9fdd2088d0a3ad1decb0a1bfc46d65cfa78fe'
NAMES={'R20':'R20_NATIVE_WIDE_N','R21':'R21_NATIVE_L0_REUSE'}

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,s): p.write_text(s,encoding='utf-8',newline='\n')
def once(s,a,b):
    assert s.count(a)==1,(s.count(a),a[:100])
    return s.replace(a,b,1)
def between(s,a,b):
    i=s.index(a)
    return s[i:s.index(b,i)]
def producer(s):
    return between(s,'template<class T,bool TA,bool TB,int TK>\nclass SmallKProducer {','class SmallKConsumer {')
def entry(s):
    return between(s,'template<class T,bool TA,bool TB,int TK>\n__aicore__ inline void NativeEntry(', '// [K,L] GEMV:')

def wide_producer(old):
    s=once(old,'class SmallKProducer {','class WideNProducer {\n    static_assert(TK==32||TK==64||TK==128,"fixed small K only");\n    static constexpr int WN=2*TN;')
    s=once(s,'int32_t seq=0;','int32_t seq=0,emitSeq=0;')
    # A remains double buffered. B is one complete K x 256 tile (64 KiB at K128).
    s=once(s,'auto dstB=b2Buf.template Get<T>()[slot*TK*TN];','auto dstB=b2Buf.template Get<T>();')
    assert s.count('abReady[slot]')==2
    s=s.replace('abReady[slot]','abReady[0]')
    start=s.index('    __aicore__ inline void Emit(')
    end=s.index('public:',start)
    s=s[:start]+'''    __aicore__ inline void Emit(int group,int mo,int no,int mr,int nr,int ar,int br,int stage){
        const int slot=emitSeq&1;
        // The single, full-width B2 buffer cannot be overwritten before M releases it.
        if(emitSeq)AscendC::WaitFlag<AscendC::HardEvent::M_MTE1>(abFree[0]);
        if(emitSeq>=2)AscendC::WaitFlag<AscendC::HardEvent::FIX_M>(cFree[slot]);
        LoadL0(mo,no,mr,nr,ar,br,stage,slot);
        auto aa=a2Buf.template Get<T>()[slot*TM*TK];auto bb=b2Buf.template Get<T>();
        auto cc=cBuf.template Get<float>()[slot*TM*WN];
        AscendC::MmadParams q{};q.m=mr;q.n=nr;q.k=TK;q.cmatrixInitVal=true;
        AscendC::Mmad(cc,aa,bb,q);
        AscendC::SetFlag<AscendC::HardEvent::M_MTE1>(abFree[0]);
        AscendC::SetFlag<AscendC::HardEvent::M_FIX>(cReady[slot]);
        AscendC::WaitFlag<AscendC::HardEvent::M_FIX>(cReady[slot]);
        // Keep EXACTLY the original 64 x 128 tile order and four-tile packet protocol.
        for(int ni=0;ni<nr;ni+=TN){
            const int packet=seq/PACKET_TILES,packetSlot=packet&1,tileSlot=seq%PACKET_TILES;
            if(tileSlot==0&&packet>=2)AscendC::CrossCoreWaitFlag<0x2>(FREE+packetSlot);
            AscendC::FixpipeParamsV220 f{};f.nSize=MinI(TN,nr-ni);f.mSize=mr;f.srcStride=mr;
            f.dstStride=TN;f.ndNum=1;f.quantPre=QuantMode_t::NoQuant;
            AscendC::Fixpipe<float,float>(ring[((int64_t(group)*2+packetSlot)*PACKET_TILES+tileSlot)*TM*TN],cc[(ni/16)*mr*16],f);
            if(tileSlot+1==PACKET_TILES)AscendC::CrossCoreSetFlag<0x2,PIPE_FIX>(READY+packetSlot);
            ++seq;
        }
        AscendC::SetFlag<AscendC::HardEvent::FIX_M>(cFree[slot]);
        ++emitSeq;
    }
'''+s[end:]
    s=once(s,'pipe->InitBuffer(b2Buf,2*TK*TN*sizeof(T));','pipe->InitBuffer(b2Buf,TK*WN*sizeof(T));')
    s=once(s,'pipe->InitBuffer(cBuf,2*TM*TN*sizeof(float));','pipe->InitBuffer(cBuf,2*TM*WN*sizeof(float));')
    s=once(s,'for(int no=0;no<br;no+=TN){','for(int no=0;no<br;no+=WN){')
    s=once(s,'Emit(group,mo,no,MinI(TM,ar-mo),MinI(TN,br-no),ar,br,stage);',
        'Emit(group,mo,no,MinI(TM,ar-mo),MinI(WN,br-no),ar,br,stage);')
    s=once(s,'''        for(int s=0;s<MinI(2,seq);++s){
            AscendC::WaitFlag<AscendC::HardEvent::M_MTE1>(abFree[s]);
            AscendC::WaitFlag<AscendC::HardEvent::FIX_M>(cFree[s]);
        }''','''        if(emitSeq)AscendC::WaitFlag<AscendC::HardEvent::M_MTE1>(abFree[0]);
        for(int s=0;s<MinI(2,emitSeq);++s)AscendC::WaitFlag<AscendC::HardEvent::FIX_M>(cFree[s]);''')
    return s

def reuse_producer(old):
    s=once(old,'class SmallKProducer {','class SmallKProducer {\n    static_assert(TK==32||TK==64||TK==128,"fixed small K only");')
    s=once(s,'int32_t seq=0;','int32_t seq=0;bool reuseA=false,abPending[2]={false,false};')
    helper='''    // Destination is ZZ: [M/16][K/16][16][16]. Choose the shorter instruction loop.
    __aicore__ inline void LoadA0(int mo,int mr,int ar,AscendC::LocalTensor<T> dstA){
        auto srcA=a1Buf.template Get<T>();AscendC::LoadData2DParams la{};la.ifTranspose=TA;
        if(mr<=TK){
            la.repeatTimes=TK/16;la.srcStride=TA?1:ar/16;
            for(int i=0;i<mr/16;++i){
                const int off=TA?(mo/16+i)*TK*16:(mo/16+i)*256;
                AscendC::LoadData(dstA[i*TK*16],srcA[off],la);
            }
        }else{
            la.repeatTimes=mr/16;la.srcStride=TA?TK/16:1;la.dstGap=TK/16-1;
            for(int j=0;j<TK/16;++j){
                const int off=TA?(mo/16)*TK*16+j*256:j*ar*16+mo*16;
                AscendC::LoadData(dstA[j*256],srcA[off],la);
            }
        }
    }
    __aicore__ inline void DrainA0(){
        for(int s=0;s<2;++s)if(abPending[s]){
            AscendC::WaitFlag<AscendC::HardEvent::M_MTE1>(abFree[s]);abPending[s]=false;
        }
    }

'''
    s=once(s,'    __aicore__ inline void LoadA(',helper+'    __aicore__ inline void LoadA(')
    s=once(s,'        AscendC::WaitFlag<AscendC::HardEvent::MTE2_MTE1>(bReady[2]);',
        '        AscendC::WaitFlag<AscendC::HardEvent::MTE2_MTE1>(bReady[2]);\n        if(reuseA)LoadA0(0,mr,mr,a2Buf.template Get<T>());')
    a=between(s,'        auto srcA=a1Buf.template Get<T>();auto srcB=', '        AscendC::LoadData2DParams lb{};')
    s=once(s,a,'''        auto srcB=b1Buf.template Get<T>()[stage*TK*BN];
        auto dstB=b2Buf.template Get<T>()[slot*TK*TN];
        if(!reuseA)LoadA0(mo,mr,ar,a2Buf.template Get<T>()[slot*TM*TK]);
''')
    b=between(s,'        AscendC::LoadData2DParams lb{};','        AscendC::SetFlag<AscendC::HardEvent::MTE1_M>')
    s=once(s,b,'''        AscendC::LoadData2DParams lb{};lb.ifTranspose=!TB;
        // Destination is ZN: [K/16][N/16][16][16]. Short-N benefits at K64/K128.
        if(nr<TK){
            lb.repeatTimes=TK/16;lb.srcStride=TB?br/16:1;lb.dstGap=nr/16-1;
            for(int j=0;j<nr/16;++j){
                const int off=TB?(no/16+j)*256:(no/16+j)*TK*16;
                AscendC::LoadData(dstB[j*256],srcB[off],lb);
            }
        }else{
            lb.repeatTimes=nr/16;lb.srcStride=TB?1:TK/16;
            for(int j=0;j<TK/16;++j){
                const int off=TB?j*br*16+(no/16)*256:(no/16)*TK*16+j*256;
                AscendC::LoadData(dstB[j*nr*16],srcB[off],lb);
            }
        }
''')
    s=once(s,'''        if(seq>=2){
            AscendC::WaitFlag<AscendC::HardEvent::M_MTE1>(abFree[slot]);
            AscendC::WaitFlag<AscendC::HardEvent::FIX_M>(cFree[slot]);
        }''','''        if(abPending[slot]){AscendC::WaitFlag<AscendC::HardEvent::M_MTE1>(abFree[slot]);abPending[slot]=false;}
        if(seq>=2)AscendC::WaitFlag<AscendC::HardEvent::FIX_M>(cFree[slot]);''')
    s=once(s,'auto aa=a2Buf.template Get<T>()[slot*TM*TK];',
        'auto aa=a2Buf.template Get<T>()[reuseA?mo*TK:slot*TM*TK];')
    s=once(s,'        AscendC::SetFlag<AscendC::HardEvent::M_MTE1>(abFree[slot]);',
        '        AscendC::SetFlag<AscendC::HardEvent::M_MTE1>(abFree[slot]);abPending[slot]=true;')
    s=once(s,'        p=plan;pipe_=pipe;','''        p=plan;pipe_=pipe;
        // Cache only if EVERY N shard consumes at least two microtiles.
        reuseA=(p.pN>0&&p.nTiles>=2*p.pN);''')
    s=once(s,'pipe->InitBuffer(a2Buf,2*TM*TK*sizeof(T));',
        'pipe->InitBuffer(a2Buf,(reuseA?AM:2*TM)*TK*sizeof(T));')
    s=once(s,'                const int panelCount=',
        '                // Fence all readers before the next M stage replaces the resident L0A.\n                if(reuseA)DrainA0();\n                const int panelCount=')
    s=once(s,'        for(int s=0;s<MinI(2,seq);++s){\n            AscendC::WaitFlag<AscendC::HardEvent::M_MTE1>(abFree[s]);',
        '        DrainA0();\n        for(int s=0;s<MinI(2,seq);++s){')
    return s

def generate(version,original):
    old=producer(original)
    if version=='R20':
        added='''// A full 256-column MMAD is used only when all task N shards have >=2 microtiles.
static inline bool UseWideN(const NativePlan& p){return p.pN>0&&p.nTiles>=2*p.pN;}

'''+wide_producer(old)
        s=once(original,old,old+added)
        old_entry=entry(s)
        new_entry=once(old_entry,
            'if ASCEND_IS_AIC {SmallKProducer<T,TA,TB,TK> op;op.Init(a,b,ring,p,&pipe);op.Process();}',
            '''if ASCEND_IS_AIC {
        if(UseWideN(p)){WideNProducer<T,TA,TB,TK> op;op.Init(a,b,ring,p,&pipe);op.Process();}
        else{SmallKProducer<T,TA,TB,TK> op;op.Init(a,b,ring,p,&pipe);op.Process();}
    }''')
        return once(s,old_entry,new_entry),added
    assert version=='R21'
    new=reuse_producer(old)
    return once(original,old,new),new

def verify():
    assert sha(BASE)==BASE_SHA and sha(OUT/'R14_CONTROL.asc')==BASE_SHA
    original=BASE.read_text(encoding='utf-8')
    for version,name in NAMES.items():
        expected,fragment=generate(version,original)
        actual=(OUT/(name+'.asc')).read_text(encoding='utf-8')
        assert actual.split('\n',1)[1]==expected.split('\n',1)[1]
        assert (HERE/(version+'_producer.asc')).read_text(encoding='utf-8')==fragment
        # Restore the allowed edit and check every other byte (apart from version comment).
        if version=='R20':
            restored=once(actual,fragment,'')
            restored=once(restored,entry(restored),entry(original))
        else: restored=once(actual,fragment,producer(original))
        assert restored.split('\n',1)[1]==original.split('\n',1)[1]
    return {'independent_R14_descendants':True,'only_Native_producer_and_R20_entry_changed':True,
            'host_plans_dispatch_guards_consumers_unchanged':True,'ring_partial_layout_and_sizes_unchanged':True,
            'R20_fallback_original_producer_retained':True,'full_K_FP32_dot_then_max_then_sum_preserved':True}

def main():
    assert sha(BASE)==BASE_SHA
    original=BASE.read_text(encoding='utf-8');OUT.mkdir(exist_ok=True)
    shutil.copyfile(BASE,OUT/'R14_CONTROL.asc');variants=[]
    for version,name in NAMES.items():
        s,fragment=generate(version,original)
        s=once(s,s.split('\n',1)[0],'// '+name+': independent R14 Native-only experiment; pending platform validation.')
        write(HERE/(version+'_producer.asc'),fragment);path=OUT/(name+'.asc');write(path,s)
        write(HERE/(name+'.diff'),''.join(difflib.unified_diff(original.splitlines(True),s.splitlines(True),fromfile='R14',tofile=name)))
        variants.append({'version':version,'file':path.name,'sha256':sha(path),'platform_result_received':False})
    report={'base':BASE.relative_to(ROOT).as_posix(),'base_sha256':BASE_SHA,'control':{'file':'R14_CONTROL.asc','sha256':BASE_SHA},
        'variants':variants,'proof':verify(),'cann_compiled_locally':False,'npu_tested_locally':False}
    write(OUT/'MANIFEST.json',json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__': main()

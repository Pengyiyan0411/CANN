"""Build two independent descendants of the user-confirmed R01 source."""
from pathlib import Path
import difflib
import hashlib
import json

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
OUT=ROOT/'BMMS_V11_R02_R03'
R01=ROOT/'BMMS_V11_SubmitPack/R01_REUSE_2X2.asc'
R01_SHA='dc372a48a8b38dcb3ee1c782f93842624945cfe0627b04b2112e70d0a949663e'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def once(s,a,b):
    assert s.count(a)==1,(s.count(a),a)
    return s.replace(a,b,1)
def write(p,s):p.write_text(s,encoding='utf-8',newline='\n')

def ring_fragment(old):
    s=old.replace('bmms11','bmms11r2').replace('BMMS11_','BMMS11R2_')
    s=once(s,'// V11 R01: real 2x2 operand reuse, K1=256 / K0=64.',
        '// V11 R02: publish a completed 2x2 macro tile using one ring credit.')
    s=once(s,'constexpr uint16_t READY=4,FREE=6;',
        'constexpr int32_t MACRO_ELEMS=4*TM*TN;\nconstexpr uint16_t READY=4,FREE=6;')
    s=once(s,'uint64_t(p.blocks)*2*TM*TN*4ULL','uint64_t(p.blocks)*2*MACRO_ELEMS*4ULL')
    assert s.count('int64_t(p.blocks)*2*TM*TN')==2
    s=s.replace('int64_t(p.blocks)*2*TM*TN','int64_t(p.blocks)*2*MACRO_ELEMS')
    s=once(s,'        AscendC::WaitFlag<AscendC::HardEvent::M_FIX>(cReady);',
        '''        AscendC::WaitFlag<AscendC::HardEvent::M_FIX>(cReady);
        const int macroSlot=seq&1;
        // One slot owns the WHOLE macro. No AIV wait between its Fixpipes.
        if(seq>=2)AscendC::CrossCoreWaitFlag<0x2>(FREE+macroSlot);''')
    s=once(s,'const int nr=MinI(TN,br-no),ci=(mo/TM)*2+no/TN,slot=seq&1;\n                if(seq>=2)AscendC::CrossCoreWaitFlag<0x2>(FREE+slot);',
        'const int nr=MinI(TN,br-no),ci=(mo/TM)*2+no/TN;')
    s=once(s,'ring[(int64_t(group)*2+slot)*TM*TN],cBuf.template Get<float>()[ci*TM*TN]',
        'ring[(int64_t(group)*2+macroSlot)*MACRO_ELEMS+ci*TM*TN],cBuf.template Get<float>()[ci*TM*TN]')
    s=once(s,'                AscendC::CrossCoreSetFlag<0x2,PIPE_FIX>(READY+slot);++seq;\n','')
    s=once(s,'        AscendC::SetFlag<AscendC::HardEvent::FIX_M>(cFree);cPending=true;',
        '''        AscendC::SetFlag<AscendC::HardEvent::FIX_M>(cFree);cPending=true;
        // READY on FIX covers every live micro-tile written above.
        AscendC::CrossCoreSetFlag<0x2,PIPE_FIX>(READY+macroSlot);++seq;''')
    # Consumer is the same numerical algorithm and iteration order as R01.
    s=once(s,'                    const int br=MinI(BN,nEnd-nBase);',
        '''                    const int br=MinI(BN,nEnd-nBase),ringSlot=seq&1;
                    AscendC::CrossCoreWaitFlag<0x2>(READY+ringSlot);''')
    s=once(s,'                            const int nr=MinI(TN,br-no),ringSlot=seq&1;\n                            AscendC::CrossCoreWaitFlag<0x2>(READY+ringSlot);',
        '                            const int nr=MinI(TN,br-no),ci=(mo/TM)*2+no/TN;')
    s=once(s,'(int64_t(group)*2+ringSlot)*TM*TN+sub*vr*TN',
        '(int64_t(group)*2+ringSlot)*MACRO_ELEMS+ci*TM*TN+sub*vr*TN')
    s=once(s,'                            AscendC::CrossCoreSetFlag<0x2,PIPE_MTE2>(FREE+ringSlot);',
        '''                            // Each AIV releases only after its LAST live micro-tile read.
                            if(mo+mr==ar&&no+nr==br)AscendC::CrossCoreSetFlag<0x2,PIPE_MTE2>(FREE+ringSlot);''')
    s=once(s,'cq.FreeTensor(c);++seq;','cq.FreeTensor(c);')
    needle='                        AscendC::Max(run[mo+sub*vr],run[mo+sub*vr],rows,vr);AscendC::PipeBarrier<PIPE_V>();\n                    }\n                }'
    s=once(s,needle,needle[:-len('                }')]+'                    ++seq;\n                }')
    # All public routing and input-side compute is unchanged after namespace normalization.
    norm=s.replace('bmms11r2','bmms11').replace('BMMS11R2_','BMMS11_')
    a=old[old.index('static inline bool Eligible('):old.index('static inline uint64_t RingBytes')]
    assert a==norm[norm.index('static inline bool Eligible('):norm.index('static inline uint64_t RingBytes')]
    a=old[old.index('    __aicore__ inline void LoadStage('):old.index('        AscendC::SetFlag<AscendC::HardEvent::M_FIX>(cReady);')]
    assert a==norm[norm.index('    __aicore__ inline void LoadStage('):norm.index('        AscendC::SetFlag<AscendC::HardEvent::M_FIX>(cReady);')]
    return s

def residual_fragment():
    old=(ROOT/'V9_impl/dense_fragment.asc').read_text(encoding='utf-8')
    assert old in (ROOT/'BMMS_V9_SubmitPack/D01_DENSE_K128.asc').read_text(encoding='utf-8')
    s=old.replace('bmms9d','bmms11d').replace('BMMS9D','BMMS11D')
    s=once(s,'// BMMS V9-D experimental full-K native Cube path.',
        '// V11 R03: D01 K128 restricted to the public-shape residual of R01.')
    s=once(s,'static inline Plan MakePlan(','''static inline bool ResidualEligible(int32_t B,int32_t M,int32_t N,int32_t K,int32_t cores){
    return B>=1&&B<=64&&cores>=1&&cores<=64&&Eligible(M,N,K)&&
        int64_t(B)*M*K<=(1LL<<26)&&int64_t(B)*N*K<=(1LL<<26)&&
        !bmms11::Eligible(B,M,N,K,cores);
}

static inline Plan MakePlan(''')
    s=once(s,'            AscendC::Mmad(cc,aa,bb,q);',
        '''            AscendC::Mmad(cc,aa,bb,q);
            // Official Mmad dependency for small output tiles, also used by R01.
            if((mr/16)*(nr/16)<10)AscendC::PipeBarrier<PIPE_M>();''')
    s=once(s,'if(B<1||B>64||cores<1||cores>64||(dtype!=1&&dtype!=2)||!Eligible(M,N,K)||\n       int64_t(B)*M*K>(1LL<<26)||int64_t(B)*N*K>(1LL<<26))return false;',
        'if((dtype!=1&&dtype!=2)||!ResidualEligible(B,M,N,K,cores))return false;')
    return s

def main():
    assert sha(R01)==R01_SHA
    original=R01.read_text(encoding='utf-8')
    old=(ROOT/'V11_impl/reuse_fragment.asc').read_text(encoding='utf-8')
    assert original.count(old)==1
    r2=ring_fragment(old);d3=residual_fragment()
    write(HERE/'macro_ring_fragment.asc',r2);write(HERE/'residual_dense_fragment.asc',d3)
    out2=once(original,old,r2)
    out2=once(out2,'if(bmms11::TryLaunch(a,b,y,','if(bmms11r2::TryLaunch(a,b,y,')
    out2=once(out2,original.split('\n',1)[0],'// R02_MACRO_RING: independent R01 descendant; macro-level output publication.')
    out3=once(original,'extern "C" void run_kernel(',d3+'\nextern "C" void run_kernel(')
    hook='    if(bmms11::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
    extra='    if(bmms11d::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
    out3=once(out3,hook,hook+extra)
    out3=once(out3,original.split('\n',1)[0],'// R03_RESIDUAL_DENSE: independent R01 descendant; D01 on the uncovered aligned domain.')
    assert out3.split('\n',1)[1].replace(d3+'\n','',1).replace(extra,'',1)==original.split('\n',1)[1]
    assert out2.replace(r2,old,1).replace('if(bmms11r2::TryLaunch','if(bmms11::TryLaunch',1).split('\n',1)[1]==original.split('\n',1)[1]
    OUT.mkdir(exist_ok=True);variants=[]
    for name,src,fragment,changes in [
        ('R02_MACRO_RING',out2,HERE/'macro_ring_fragment.asc','macro-level C publication; same R01 dispatch and arithmetic'),
        ('R03_RESIDUAL_DENSE',out3,HERE/'residual_dense_fragment.asc','R01 then D01 residual; small-output PIPE_M dependency')]:
        p=OUT/(name+'.asc');write(p,src)
        assert src.count('extern "C" void run_kernel(')==1 and '#define ASCENDC_CUBE_ONLY' not in src
        write(HERE/(name+'.diff'),''.join(difflib.unified_diff(original.splitlines(True),src.splitlines(True),fromfile='R01',tofile=name)))
        variants.append({'name':name,'file':p.name,'sha256':sha(p),'fragment_sha256':sha(fragment),'changes':changes,
            'cann_compiled_locally':False,'npu_tested_locally':False,'submitted_result_received':False})
    manifest={'base':'R01_REUSE_2X2','base_sha256':R01_SHA,'independent_siblings':True,
        'R01_platform_evidence':'user explicitly labelled 15/15 Pass; no platform source digest',
        'R02_ring_bytes_per_group':262144,'R01_ring_bytes_per_group':65536,
        'known_numerical_limitations_remain':True,'variants':variants}
    write(OUT/'MANIFEST.json',json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest,indent=2))

if __name__=='__main__':main()

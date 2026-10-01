from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parents[1];H=R/'V12_npu_lab/harness'
raw=(R/'BMMS_V12/v12_baseline_r12.asc').read_bytes();sha=hashlib.sha256(raw).hexdigest()
assert sha=='a845fd9538fe71d5f6284fced34781d8fb7e997105c51065a84b344818ddbd2b'
s=raw.decode().replace('\r\n','\n');a=s.index('namespace bmms_c8p43 {');b=s.index('// BMMS_C8P43_END',a)+len('// BMMS_C8P43_END')
mod=s[a:b].replace('bmms_c8p43','bmms1215').replace('BMMS_C8P43','BMMS1215')
mod=mod.replace('return uint64_t(p.cube.M)*p.cube.K*2ULL;','return 0;').replace('return uint64_t(p.cube.K)*p.cube.N*2ULL;','return 0;')
mod=mod.replace('uint64_t(PACK_SLOTS)*PACK_SLOT_ELEMS*2ULL+','0ULL+')
# No prepack instructions or global pack barrier exist in this variant.
a=mod.index('// Both FP16 and BF16 are copied');b=mod.index('class MaskedRowMaxConsumer',a);mod=mod[:a]+mod[b:]
a=s.index('template<class T,bool TA,bool TB>\nclass ReuseProducer');b=s.index('class RowMaxConsumer',a)
prod=s[a:b].replace('ReuseProducer','DirectProducer')
prod=prod.replace('AscendC::TPipe* pipe_;Plan p;','AscendC::TPipe* pipe_;Plan p;int realM,realN,realK;')
prod=prod.replace('const Plan& plan,AscendC::TPipe* pipe){\n        p=plan;pipe_=pipe;', 'const RaggedPlan& plan,AscendC::TPipe* pipe){\n        p=plan.cube;realM=plan.realM;realN=plan.realN;realK=plan.realK;pipe_=pipe;')
prod=prod.replace('int64_t(p.B)*p.M*p.K);','int64_t(p.B)*realM*realK);').replace('int64_t(p.B)*p.K*p.N);','int64_t(p.B)*realK*realN);')
a=prod.index('        AscendC::Nd2NzParams qa');b=prod.index('        AscendC::SetFlag<AscendC::HardEvent::MTE2_MTE1>',a)
prod=prod[:a]+'''        const int liveM=MinI(ar,realM-m0),liveN=MinI(br,realN-n0),liveK=MinI(kr,realK-k0);
        // ND2NZ zero-fills only the physical column tail within C0. It does
        // not initialize missing rows or the extra 16 K words up to K%32.
        // Clear the compact L1 edge tile before copying its real rectangle.
        const bool padA=liveM<ar||liveK<kr,padB=liveN<br||liveK<kr;
        if(padA)AscendC::InitConstValue(aa,{1,static_cast<uint16_t>(ar*kr/16),0,T(0.0f)});
        if(padB)AscendC::InitConstValue(bb,{1,static_cast<uint16_t>(br*kr/16),0,T(0.0f)});
        if(padA||padB)AscendC::PipeBarrier<PIPE_MTE2>();
        AscendC::Nd2NzParams qa{};qa.ndNum=1;
        qa.nValue=TA?liveK:liveM;qa.dValue=TA?liveM:liveK;
        qa.srcDValue=TA?realM:realK;qa.dstNzC0Stride=TA?kr:ar;qa.dstNzNStride=1;
        const int64_t ai=int64_t(batch)*realM*realK+(TA?int64_t(k0)*realM+m0:int64_t(m0)*realK+k0);
        AscendC::DataCopy(aa,a[ai],qa);
        AscendC::Nd2NzParams qb{};qb.ndNum=1;
        qb.nValue=TB?liveN:liveK;qb.dValue=TB?liveK:liveN;
        qb.srcDValue=TB?realK:realN;qb.dstNzC0Stride=TB?br:kr;qb.dstNzNStride=1;
        const int64_t bi=int64_t(batch)*realK*realN+(TB?int64_t(n0)*realK+k0:int64_t(k0)*realN+n0);
        AscendC::DataCopy(bb,b[bi],qb);
'''+prod[b:]
prod='using Plan=CubePlan;\nconstexpr int K1=bmms11r2::K1,K0=bmms11r2::K0;\n'+prod
mod=mod.replace('class MaskedRowMaxConsumer {',prod+'\nclass MaskedRowMaxConsumer {',1)
mod=mod.replace('// Reuse the frozen R25 producer itself, not a modified copy.\n        bmms11r2::ReuseProducer<T,TA,TB> op;\n        op.Init(ap,bp,ring,p.cube,&pipe);\n        AscendC::CrossCoreWaitFlag<0x2>(PACK_TO_CUBE);','// Real physical GM strides; only local L1 edge tiles need padding.\n        DirectProducer<T,TA,TB> op;\n        op.Init(a,b,ring,p,&pipe);')
mod=mod.replace('        AscendC::TBuf<AscendC::TPosition::VECCALC> packBuf;\n        pipe.InitBuffer(packBuf,PACK_SLOTS*PACK_SLOT_ELEMS*2);\n        PackInputs(a,b,ap,bp,p,&pipe,packBuf);\n','')
assert 'PackInputs(' not in mod and 'op.Init(a,b,ring,p,&pipe)' in mod and 'realM=plan.realM' in prod
frag=('// BMMS1215_BEGIN\n'+mod+'\n\n').encode();anchor=b'extern "C" void run_kernel(GM_ADDR a,const TensorGroupInfo& ia,'
idx=raw.index(b'    if(bmms_c8p43::TryLaunch');end=raw.index(b'\n',idx)+1;line=raw[idx:end];hook=line.replace(b'bmms_c8p43::',b'bmms1215::')
data=raw.replace(anchor,frag+anchor,1).replace(line,hook+line,1)
assert data.replace(frag,b'',1).replace(hook,b'',1)==raw
name='v12_r15_case8_direct_l1.asc';(R/'BMMS_V12'/name).write_bytes(data);(H/'r15.asc').write_bytes(data)
j=dict(candidate=name,parent='v12_baseline_r12.asc',parent_sha256=sha,sha256=hashlib.sha256(data).hexdigest(),parent_recovered_byte_for_byte=True,status='experimental, pending device validation',L1_bytes=393216,L0A_bytes=32768,L0B_bytes=65536,L0C_bytes=131072,macro_and_plan_unchanged=True,removed='whole A/B workspace padding and pack barriers')
(R/'BMMS_V12/v12_r15_manifest.json').write_text(json.dumps(j,indent=2)+'\n')
e=(H/'event_bench_r14.asc').read_text().replace('1214','1215').replace('"r14"','"r15"')
(H/'event_bench_r15.asc').write_text(e,newline='\n')
c=H/'CMakeLists.txt';st=c.read_text()
if 'add_executable(event_bench_r15' not in st:
 a=st.index('add_executable(event_bench_r14');st+=st[a:].replace('r14','r15');c.write_text(st,newline='\n')
print(json.dumps(j,indent=2))

from pathlib import Path
import json,hashlib
R=Path(__file__).resolve().parents[1]; H=R/'V12_npu_lab/harness'
src=R/'BMMS_V12/v12_r12_splitk_adaptive_merge.asc'; data=src.read_bytes()
assert hashlib.sha256(data).hexdigest()=='a845fd9538fe71d5f6284fced34781d8fb7e997105c51065a84b344818ddbd2b'
(R/'BMMS_V12/v12_baseline_r12.asc').write_bytes(data)
p=R/'BMMS_V12/MAINLINE.json'; j=json.loads(p.read_text())
j.update(accepted_sota='v12_baseline_r12.asc',accepted_sha256=hashlib.sha256(data).hexdigest(),accepted_version='v12_r12',previous_sota='v12_baseline_r03.asc',acceptance_basis='User confirms Case15 stable around 11.5 us, other cases essentially unaffected; no complete new 15-case table supplied',naming='v12_rxx; r12 accepted after Judge feedback',next_action='Case8: measure true padded-route phases, then device-screen structural candidates derived from r12')
for c in j['candidates']:
    if c['version']=='v12_r12': c['status']='accepted after user Judge feedback: Case15 stable around 11.5 us; others essentially unaffected'
p.write_text(json.dumps(j,indent=2)+'\n')
(R/'BMMS_V12/v12_r12_JUDGE_FEEDBACK.md').write_text('# r12 已确认为主线\n\n用户反馈：Case15 稳定在约 11.5 μs，其余点基本无影响。该值是用户概述，未提供这一轮完整 15 点表。\n\n冻结源文件 `v12_baseline_r12.asc` 与已提交 r12 逐字节一致。r03 保留为历史回退；后续 Case8 候选以 r12 为父版本。\n',encoding='utf-8')
g=(H/'generate_followup.py').read_text();a=g.index('specs=[]');b=g.index('manifest=[];records=[]')
g=g[:a]+'''specs=[]
for M,N,K in [(1041,1105,1064),(1537,1599,1128),(2047,2033,1272)]:
    for dt,ta,tb in itertools.product([1,2],[0,1],[0,1]):
        specs.append(dict(id=len(specs),label='c8_screen',B=1,M=M,N=N,K=K,dtype=dt,ta=ta,tb=tb,pattern='random'))
'''+g[b:];g=g.replace("default='cases_followup'","default='cases_c8'").replace('720928','1330928')
a=g.index('sets={');b=g.index('for name,ids in sets.items():',a)
g=g[:a]+"sets={'manifest':range(len(manifest)),'smoke':[0,3,4,7,8,16], 'screen':[0,1,2,3,8,9,10,11,16,17,18,19]}\n"+g[b:]
(H/'generate_c8.py').write_text(g,newline='\n')
# Standalone phase diagnostic: one mixed kernel per sample, no submission changes.
kernel='''
namespace c8diag {
template<class T,bool TA,bool TB,int PHASE>
__aicore__ inline void Entry(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ap,GM_ADDR bp,GM_ADDR ring,GM_ADDR part,bmms_c8p43::RaggedPlan p){
    AscendC::TPipe pipe;
    if ASCEND_IS_AIC {
        if(PHASE!=2)AscendC::CrossCoreWaitFlag<0x2>(bmms_c8p43::PACK_TO_CUBE);
        if(PHASE!=1){bmms11r2::ReuseProducer<T,TA,TB> op;op.Init(ap,bp,ring,p.cube,&pipe);op.Process();}
    }
    if ASCEND_IS_AIV {
        if(PHASE!=2){
            AscendC::TBuf<AscendC::TPosition::VECCALC> pack;
            pipe.InitBuffer(pack,bmms_c8p43::PACK_SLOTS*bmms_c8p43::PACK_SLOT_ELEMS*2);
            bmms_c8p43::PackInputs(a,b,ap,bp,p,&pipe,pack);
        }
        if(PHASE!=1){bmms_c8p43::MaskedRowMaxConsumer op;op.Init(ring,part,y,p,&pipe);op.Process();}
    }
}
}
#define KERN(NAME,T,TA,TB,P) __global__ __mix__(1,2) __aicore__ __schedmode__(1) void NAME(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ap,GM_ADDR bp,GM_ADDR r,GM_ADDR pt,bmms_c8p43::RaggedPlan p){c8diag::Entry<T,TA,TB,P>(a,b,y,ap,bp,r,pt,p);}
'''
for phase in [1,2]:
 for typ,T in [('f16','half'),('b16','bfloat16_t')]:
  for ta,tb in [(0,0),(0,1),(1,0),(1,1)]:
   kernel+=f'KERN(c8diag{phase}_{typ}_{"t" if ta else "n"}{"t" if tb else "n"},{T},{str(bool(ta)).lower()},{str(bool(tb)).lower()},{phase})\n'
kernel+='#undef KERN\n'
e=(H/'event_bench_r12.asc').read_text(); start=e.index('static void launch_direct');end=e.index('\nint main(',start)
launch='''static void launch_direct(int phase,void* a,void* b,void* y,void* ws,const bmms_c8p43::RaggedPlan& plan,int dt,bool ta,bool tb,aclrtStream stream){
    auto p=plan;auto ap=(uint8_t*)ws;auto bp=ap+bmms_c8p43::ABytes(p);auto ring=bp+bmms_c8p43::BBytes(p);auto part=ring+bmms_c8p43::RingBytes(p);
#define CALL(NAME) NAME<<<p.cube.blocks,nullptr,stream>>>((uint8_t*)a,(uint8_t*)b,(uint8_t*)y,ap,bp,ring,part,p)
#define DISPATCH(NS) \\
    if(dt==1){ \\
        if(!ta&&!tb){CALL(NS##_f16_nn);}else if(!ta&&tb){CALL(NS##_f16_nt);} \\
        else if(ta&&!tb){CALL(NS##_f16_tn);}else{CALL(NS##_f16_tt);} \\
    }else{ \\
        if(!ta&&!tb){CALL(NS##_b16_nn);}else if(!ta&&tb){CALL(NS##_b16_nt);} \\
        else if(ta&&!tb){CALL(NS##_b16_tn);}else{CALL(NS##_b16_tt);} \\
    }
    if(phase==0){DISPATCH(bmms_c8p43);}else if(phase==1){DISPATCH(c8diag1);}else{DISPATCH(c8diag2);}
#undef DISPATCH
#undef CALL
}
'''
e=e[:start]+kernel+launch+e[end:]
e=e.replace('!bmms1212::Eligible','!bmms_c8p43::Eligible').replace('bmms23::MakePlan(B,M,N,K,cores)','bmms_c8p43::MakePlan(M,N,K,cores,ta,tb)').replace('(bmms23::WorkspaceBytes(p)+uint64_t(p.M)*sizeof(float))','bmms_c8p43::WorkspaceBytes(p)')
e=e.replace('launch_direct(!aa&&(warm%2)', 'launch_direct(0')
e=e.replace('for(int order=0;order<2;++order){','for(int order=0;order<3;++order){').replace('const bool label=((order+w)%2)!=0,candidate=!aa&&label;', 'const int phase=(order+w)%3;')
e=e.replace('launch_direct(candidate','launch_direct(phase')
e=e.replace('for(int j=0;j<B;++j){','for(int j=0;phase!=1&&j<B;++j){')
a=e.index('                std::fprintf(out,');b=e.index('                std::fflush(out);',a)
e=e[:a]+'''                std::fprintf(out,"{\\"case\\":%d,\\"window\\":%d,\\"phase\\":%d,\\"pM\\":%d,\\"pN\\":%d,\\"blocks\\":%d,\\"calls\\":%d,\\"device_stream_us_per_call\\":%.8f,\\"max_tolerance_ratio\\":%.9g}\\n",id,w,phase,p.cube.pM,p.cube.pN,p.cube.blocks,batchCalls,ms*1000.0/batchCalls,maxRatio);
'''+e[b:]
# Exactly verify pack-only output against independent raw physical padding.
mark='                double maxRatio=0;'
verify='''                if(phase==1){
                    const bmms_c8p43::PackDesc descs[]={p.a,p.b};
                    for(int side=0;side<2;++side){
                        const auto& d=descs[side];auto& original=side?bh:ah;
                        size_t sz=size_t(d.dstRows)*d.dstCols*2;std::vector<uint8_t> packed(sz),expected(sz,0);
                        for(int row=0;row<d.srcRows;++row)std::memcpy(expected.data()+size_t(row)*d.dstCols*2,original.data()+size_t(row)*d.srcCols*2,d.srcCols*2);
                        ck(aclrtMemcpy(packed.data(),sz,(uint8_t*)ws+(side?bmms_c8p43::ABytes(p):0),sz,ACL_MEMCPY_DEVICE_TO_HOST),"pack verify");
                        if(packed!=expected){std::fprintf(stderr,"pack mismatch case %d side %d\\n",id,side);return 3;}
                    }
                }
'''
e=e.replace(mark,verify+mark);(H/'phase_c8.asc').write_text(e,newline='\n')
c=H/'CMakeLists.txt';s=c.read_text()
if 'add_executable(phase_c8' not in s:
 s+='''
add_executable(phase_c8 phase_c8.asc)
target_compile_definitions(phase_c8 PRIVATE BMMS_KERNEL_HEADER="r12.asc" BMMS_VARIANT="r12")
target_link_libraries(phase_c8 PRIVATE tiling_api register platform unified_dlog dl m graph_base)
target_include_directories(phase_c8 PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_options(phase_c8 PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=${NPU_ARCH}>)
''';c.write_text(s,newline='\n')
print('r12 promoted; phase harness generated')

from pathlib import Path
import json,hashlib,shutil
r=Path(__file__).resolve().parents[1];o=r/'BMMS_V12';lab=r/'V12_npu_lab';h=lab/'harness'
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(x):return hashlib.sha256(x).hexdigest()
f=r/'V12_results/2026-09-28_r24_feedback';f.mkdir(parents=True,exist_ok=True)
times=[2.29,4.72,5.36,6.46,6.50,14.66,9.48,46.36,69.55,84.42,1160,1500,15.13,13.75,11.13]
best=[1.22,1.58,2.13,2.92,1.89,7.07,3.68,14.88,50.68,72.39,74.82,91.20,5.14,5.40,4.05]
dump(f/'RESULTS.json',dict(version='v12_r24',attribution='Unique preceding diagnostic inferred from conversation; no platform source hash',
    source_sha256=sha((o/'v12_r24_probe_r22_complement.asc').read_bytes()),all_pass=True,
    cases=[dict(case=i+1,latency_us=t,display='1.16ms' if i==10 else '1.50ms' if i==11 else f'{t:.2f}us',best_us=best[i],pass_=True,error_pct=0) for i,t in enumerate(times)],
    decode={'11':'HIT','12':'HIT'},conclusion='Both match Eligible AND !Prefer AND ValidPlan with workspace allocation success; r22 Prefer excluded both.'))
shutil.copyfile(Path('E:/Tencent Files/3232896164/nt_qq/nt_data/Pic/2026-09/Ori/31b17262ba025e4a8c1b98e68023377b.png'),f/'judge.png')
(f/'ANALYSIS.md').write_text('''# r24：互补条件双阳性

全部15点Pass。11显示1.16ms、12显示1.50ms（截图精度只有0.01ms），与历史原R06单组压力吻合。结合r23两点无信号，现在有正证据确认本次输入满足r22范围、计划和分配条件，且Prefer=false。故r22的物理跨度门槛排除了两个目标点。

约束是 `(!ta || M%64==0) && ((tb?K:N)%64==0)`：NN只推出N对齐，NT只推出K对齐，TN推出M/N对齐，TT推出M/K对齐。不能声称三维全对齐、确切shape或布局已经知道。转述的原shape范围仍保留。

覆盖诊断在此结束。r19仍为主线；不直接取消NZ门槛（此前无门槛NZ初筛存在明显退化）。下一轮针对对齐物理跨度的原R06测试整宏块MMAD和整块Fixpipe写回，原任务划分、K累加顺序、双缓冲与maxN→sumM数学顺序保持。
''',encoding='utf-8')
base=(o/'v12_baseline_r19.asc').read_bytes();s=base.decode()
old=(o/'v12_r06_case9_macro_mmad.asc').read_text(encoding='utf-8')
a=old.index('// BMMS1206_BEGIN');b=old.index('// BMMS1206_END',a)+len('// BMMS1206_END')
module=old[a:b].replace('1206','1225')
module=module.replace('return B==1&&M>=1024&&N>=1024&&K>=1024&&K<1536&&bmms11r2::Eligible(B,M,N,K,cores);',
 'return B==1&&M>=1024&&M<2048&&N>=2048&&N<=8192&&K>=1536&&K<4096&&bmms11r2::Eligible(B,M,N,K,cores);')
module=module.replace('static inline bool ReusesA(const Plan& p){return p.nTiles/p.pN>=2;}',
 'static inline bool AlignedPitch(int M,int N,int K,bool ta,bool tb){return (!ta||M%64==0)&&((tb?K:N)%64==0);}')
module=module.replace('if((dtype!=1&&dtype!=2)||!Eligible(B,M,N,K,cores))return false;',
 'if((dtype!=1&&dtype!=2)||!Eligible(B,M,N,K,cores)||!AlignedPitch(M,N,K,ta,tb))return false;')
module=module.replace('if(!ReusesA(p))return false;','')
a=module.index('        for(int mo=0;mo<ar;mo+=TM){',module.index('const int macroSlot=seq&1;'))
b=module.index('        AscendC::SetFlag<AscendC::HardEvent::FIX_M>',a)
module=module[:a]+'''        // One contiguous ND macro in each ring slot; consumer uses BN row pitch.
        AscendC::FixpipeParamsV220 f{};f.nSize=br;f.mSize=ar;f.srcStride=ar;
        f.dstStride=BN;f.ndNum=1;f.quantPre=QuantMode_t::NoQuant;
        AscendC::Fixpipe<float,float>(ring[(int64_t(group)*2+macroSlot)*MACRO_ELEMS],cBuf.template Get<float>(),f);
'''+module[b:]
module=module.replace('No AIV wait between its Fixpipes.','One Fixpipe publishes all live cells.').replace('READY on FIX covers every live micro-tile written above.','READY on FIX covers the complete ND macro written above.')
a=s.index('class RowMaxConsumer {',s.index('namespace bmms11r2 {'));b=s.index('\n};',a)+len('\n};')
consumer=s[a:b]
consumer=consumer.replace('+ci*TM*TN+sub*vr*TN;','+(mo+sub*vr)*BN+no;')
consumer=consumer.replace('uint32_t((TN-nr)*4),uint32_t((TN-nr)/8)','uint32_t((BN-nr)*4),uint32_t((TN-nr)/8)')
assert consumer!=s[a:b]
idx=module.index('} // namespace bmms1225');module=module[:idx]+consumer+'\n'+module[idx:]
module=module.replace('bmms11r2::RowMaxConsumer op;','RowMaxConsumer op;')
module=('\n'+module+'\n\n').encode()
idx=base.index(b'extern "C" void run_kernel');new=base[:idx]+module+base[idx:]
hook=b'    if(bmms1225::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
idx=new.index(b'    if(bmms11r2::TryLaunch(a,b,y,');new=new[:idx]+hook+new[idx:]
assert new.replace(module,b'',1).replace(hook,b'',1)==base
name='v12_r25_dense_macro_store.asc';(o/name).write_bytes(new);(h/'r25.asc').write_bytes(new)
dump(o/'v12_r25_manifest.json',dict(version='v12_r25',file=name,sha256=sha(new),parent='v12_baseline_r19.asc',parent_sha256=sha(base),status='experimental; validation pending',change='Full macro MMAD and single ND Fixpipe; same original R06 plan; r24 aligned-pitch domain'))

t=(h/'event_c1112_nz.asc').read_text(encoding='utf-8')
a=t.index('static bmms1219::RaggedPlan');b=t.index('\nint main(',a)
t=t[:a]+'''static bool eligible(int B,int M,int N,int K,int dt,int cores){
 return (dt==1||dt==2)&&bmms1225::Eligible(B,M,N,K,cores);
}
static void launch_direct(bool candidate,void* a,void* b,void* y,void* ws,
 const bmms11r2::Plan& plan,int dt,bool ta,bool tb,aclrtStream stream){
 auto p=plan;auto ring=(uint8_t*)ws;auto part=ring+bmms11r2::RingBytes(p);
#define CALL(NAME) NAME<<<p.blocks,nullptr,stream>>>((uint8_t*)a,(uint8_t*)b,(uint8_t*)y,ring,part,p)
#define DISPATCH(NS) \\
 if(dt==1){if(!ta&&!tb){CALL(NS##_f16_nn);}else if(!ta&&tb){CALL(NS##_f16_nt);}else if(ta&&!tb){CALL(NS##_f16_tn);}else{CALL(NS##_f16_tt);}} \\
 else{if(!ta&&!tb){CALL(NS##_b16_nn);}else if(!ta&&tb){CALL(NS##_b16_nt);}else if(ta&&!tb){CALL(NS##_b16_tn);}else{CALL(NS##_b16_tt);}}
 if(candidate){DISPATCH(bmms1225);}else{DISPATCH(bmms11r2);}
#undef CALL
#undef DISPATCH
}
'''+t[b:]
t=t.replace('        nzPlan=bmms1219::MakePlan(M,N,K,cores,ta,tb);\n','')
t=t.replace('        if(bmms1219::WorkspaceBytes(nzPlan)>bmms1219::MAX_WORKSPACE_BYTES||bmms1219::AppUbBytes(nzPlan)>bmms1219::UB_BUDGET_BYTES)return 4;\n','')
t=t.replace('bmms11r2::WorkspaceBytes(p)+bmms1219::WorkspaceBytes(nzPlan)','bmms11r2::WorkspaceBytes(p)')
t=t.replace('candidate?"nz":"nd"','candidate?"macro_store":"r19"')
(h/'event_bench_r25.asc').write_text(t,encoding='utf-8',newline='\n')
cm=h/'CMakeLists.txt';t=cm.read_text(encoding='utf-8')
if 'add_executable(bench_r25 ' not in t:
 t+='''
add_executable(bench_r25 main.asc)
add_executable(event_bench_r25 event_bench_r25.asc)
add_executable(sanitize_r25 main.asc)
foreach(t IN ITEMS bench_r25 event_bench_r25 sanitize_r25)
 target_compile_definitions(${t} PRIVATE BMMS_KERNEL_HEADER="r25.asc" BMMS_VARIANT="r25")
 target_link_libraries(${t} PRIVATE tiling_api register platform unified_dlog dl m graph_base)
 target_include_directories(${t} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
 target_compile_options(${t} PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=${NPU_ARCH}>)
endforeach()
target_compile_options(sanitize_r25 PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--cce-enable-sanitizer> $<$<COMPILE_LANGUAGE:ASC>:-gline-tables-only>)
add_custom_target(r25_build DEPENDS bench_r25 event_bench_r25)
'''
cm.write_text(t,encoding='utf-8',newline='\n')
# Additional aligned-pitch BOTH-tail value controls, both storage dtypes.
t=(h/'generate_c1112_screen.py').read_text(encoding='utf-8').replace('cases_c1112_screen','cases_r25_values').replace('2092812','2092825')
a=t.index('shapes=');b=t.index('for j,pattern',a);t=t[:a]+t[b:]
t=t.replace('K=1568','K=1600').replace('ta=j//2,tb=j%2','ta=0,tb=1')
t=t.replace("'profile':[4], 'sanitize':[34,35], 'screen':range(32)","'profile':[2], 'sanitize':[2,3], 'screen':range(8)")
(h/'generate_r25_values.py').write_text(t,encoding='utf-8',newline='\n')
main=json.loads((o/'MAINLINE.json').read_text(encoding='utf-8'));assert main['accepted_version']=='v12_r19'
main['active_diagnostic'].update(status='Judge all15 Pass; Case11 1.16ms / Case12 1.50ms: both HIT, Prefer=false confirmed',feedback='../V12_results/2026-09-28_r24_feedback/RESULTS.json',historical=True)
main.update(recommended_candidate=None,next_action='End coverage probing; evaluate r25 dense macro store locally; r19 accepted');dump(o/'MAINLINE.json',main)
p=o/'v12_r24_manifest.json';m=json.loads(p.read_text(encoding='utf-8'));m.update(status='Judge all15 Pass; both target points HIT, aligned physical pitch predicate confirmed',feedback='../V12_results/2026-09-28_r24_feedback/RESULTS.json');dump(p,m)
print(name,sha(new))

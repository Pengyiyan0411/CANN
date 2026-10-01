from pathlib import Path
import json,hashlib,shutil
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V12';lab=root/'V12_npu_lab/narrow_dense'
base=(v/'v12_baseline_r33.asc').read_bytes();s=base.decode()
r37=(v/'v12_r37_dense_singlewave_plan.asc').read_bytes().decode()
a=r37.index('// BMMS1237_PLAN_BEGIN');b=r37.index('// BMMS1237_PLAN_END',a)+len('// BMMS1237_PLAN_END')
policy=r37[a:b]+'\n'
mod='''// BMMS1239_BEGIN
namespace bmms1239 {
using Plan=bmms11r2::Plan;
static inline bool Matched(int B,int M,int N,int K,int dtype,bool ta,bool tb,int cores){
    if((dtype!=1&&dtype!=2)||!bmms1230::Eligible(B,M,N,K,cores)||
       !bmms1230::AlignedPitch(M,N,K,ta,tb))return false;
    const auto family=bmms8::Classify(B,M,N,K,ta,tb);
    if(family==bmms8::Family::Resident||family==bmms8::Family::Tiny)return false;
    const auto old=bmms11r2::MakePlan(B,M,N,K,cores);
    const auto next=bmms1237::MakePlan(B,M,N,K,cores);
    return old.pM!=next.pM||old.pN!=next.pN||old.tasks!=next.tasks||old.blocks!=next.blocks;
}
static inline Plan StressPlan(int B,int M,int N,int K,int cores){
    auto p=bmms11r2::MakePlan(B,M,N,K,cores);
    // Real computation, one Cube group. No skipped arithmetic or stale output.
    p.pM=1;p.pN=1;p.tasks=B;p.blocks=1;return p;
}
static inline bool TryLaunch(GM_ADDR a,GM_ADDR b,GM_ADDR y,int B,int M,int N,int K,
    int dtype,bool ta,bool tb,int cores,aclrtStream stream){
    if(!Matched(B,M,N,K,dtype,ta,tb,cores))return false;
    const auto p=StressPlan(B,M,N,K,cores);uint8_t* ws=nullptr;
    if(aclrtMalloc(reinterpret_cast<void**>(&ws),bmms11r2::WorkspaceBytes(p),ACL_MEM_MALLOC_HUGE_FIRST)!=ACL_SUCCESS)std::abort();
    auto part=ws+bmms11r2::RingBytes(p);
#define BMMS1239_CALL(NAME) NAME<<<p.blocks,nullptr,stream>>>(a,b,y,ws,part,p)
    if(dtype==1){
        if(!ta&&!tb){BMMS1239_CALL(bmms1230_f16_nn);}else if(!ta&&tb){BMMS1239_CALL(bmms1230_f16_nt);}
        else if(ta&&!tb){BMMS1239_CALL(bmms1230_f16_tn);}else{BMMS1239_CALL(bmms1230_f16_tt);}
    }else{
        if(!ta&&!tb){BMMS1239_CALL(bmms1230_b16_nn);}else if(!ta&&tb){BMMS1239_CALL(bmms1230_b16_nt);}
        else if(ta&&!tb){BMMS1239_CALL(bmms1230_b16_tn);}else{BMMS1239_CALL(bmms1230_b16_tt);}
    }
#undef BMMS1239_CALL
    if(aclrtSynchronizeStream(stream)!=ACL_SUCCESS)std::abort();
    if(aclrtFree(ws)!=ACL_SUCCESS)std::abort();return true;
}
}
// BMMS1239_END
'''
payload=policy+'\n'+mod+'\n';idx=s.index('extern "C" void run_kernel');s=s[:idx]+payload+s[idx:]
hook='    if(bmms1239::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
idx=s.index('    if(bmms1230::TryLaunch');s=s[:idx]+hook+s[idx:]
assert s.replace(payload,'',1).replace(hook,'',1).encode()==base
name='v12_r39_probe_r37_plan_change.asc';(v/name).write_bytes(s.encode());(lab/'r39.asc').write_bytes(s.encode())
main=(lab/'main.asc').read_text();a=main.index('        bool target=false;');b=main.index('        double wall=',a)
main=main[:a]+'''        const bool target=bmms1239::Matched(B,M,N,K,dt,ta,tb,cores);
        const auto old=bmms11r2::MakePlan(B,M,N,K,cores),next=bmms1237::MakePlan(B,M,N,K,cores);
        std::printf("PROBE case=%d hit=%d old=%dx%d/%d/%d next=%dx%d/%d/%d\\n",id,int(target),old.pM,old.pN,old.tasks,old.blocks,next.pM,next.pN,next.tasks,next.blocks);
'''+main[b:]
main=main.replace('r06_guard','r39_hit');(lab/'main_r39.asc').write_text(main)
cm=(lab/'CMakeLists.txt').read_text(encoding='utf-8')
if 'add_executable(bench_r39' in cm:cm=cm[:cm.index('add_executable(bench_r39')]
cm+='''
add_executable(bench_r39 main_r39.asc)
target_compile_definitions(bench_r39 PRIVATE BMMS_KERNEL_HEADER="r39.asc" BMMS_VARIANT="r39")
target_link_libraries(bench_r39 PRIVATE tiling_api register platform unified_dlog dl m graph_base)
target_include_directories(bench_r39 PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_options(bench_r39 PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=dav-2201>)
''';(lab/'CMakeLists.txt').write_text(cm)
manifest=dict(version='v12_r39',kind='diagnostic only; intentionally slower on predicate HIT',parent='v12_baseline_r33.asc',sha256=hashlib.sha256(s.encode()).hexdigest(),predicate='r37 full route guards AND (old/new pM,pN,tasks,blocks differ)',new_device_entries=0,source_byte_recovery=True,status='pending NPU calibration')
(v/'v12_r39_manifest.json').write_text(json.dumps(manifest,indent=2));print(json.dumps(manifest))

feedback=root/'V12_results/2026-09-29_r37_feedback';feedback.mkdir(exist_ok=True)
img=Path(r'E:\Tencent Files\3232896164\nt_qq\nt_data\Pic\2026-09\Ori\145f9f625692d3f77bb3198f800da959.png')
if img.exists():shutil.copyfile(img,feedback/'judge_r37.png')
values=[2.16,4.65,5.27,6.47,6.62,15.23,9.54,46.92,66.38,79.57,97.32,116.02,15.10,13.82,11.14]
old=json.loads((root/'V12_results/2026-09-28_r33_feedback/RESULTS.json').read_text())
rows=[]
for prior,t in zip(old['rows'],values):
 rows.append(dict(case=prior['case'],status='Pass',displayed_error_percent=0.0,latency_us=t,platform_best_us=prior['platform_best_us'],r33_us=prior['latency_us'],change_pct=100*(t/prior['latency_us']-1)))
result=dict(version='v12_r37',version_attribution='Inferred from direct response to r37 delivery; no version/hash label visible in screenshot',source_sha256=hashlib.sha256((v/'v12_r37_dense_singlewave_plan.asc').read_bytes()).hexdigest(),source_hash_visible_in_screenshot=False,source='user screenshot',independent_runs=1,all_15_pass=True,screenshot_copied=img.exists(),rows=rows,decision='No demonstrated gain; do not promote r37. Keep r33. One timing sample cannot distinguish drift/regression or identify whether the plan changed; prepare calibrated r39 predicate probe.')
(feedback/'RESULTS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
mainline=json.loads((v/'MAINLINE.json').read_text());assert mainline['accepted_sota']=='v12_baseline_r33.asc'
for candidate in mainline['candidates']:
 if candidate['version']=='v12_r37':candidate['status']='Judge all15 Pass; Case11=97.32us, Case12=116.02us; no demonstrated gain; not promoted';candidate['judge_feedback']='../V12_results/2026-09-29_r37_feedback/RESULTS.json'
mainline['recommended_candidate']=None;mainline['latest_judge_feedback']='../V12_results/2026-09-29_r37_feedback/RESULTS.json';mainline['latest_experiment_report']='../V12_npu_lab/results/narrow_dense_20260929/REPORT.md'
mainline['next_action']='Calibrate then submit one r39 predicate diagnostic, matching full r37 guards and comparing original/new plans. Keep r33 accepted.'
(v/'MAINLINE.json').write_text(json.dumps(mainline,ensure_ascii=False,indent=2)+'\n')
m=json.loads((v/'v12_r37_manifest.json').read_text());m['status']='Judge all15 Pass, no demonstrated gain on11/12; not promoted';m['judge_feedback']='../V12_results/2026-09-29_r37_feedback/RESULTS.json';(v/'v12_r37_manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
for p,rel in [(v/'v12_r37_README.md','../V12_results/2026-09-29_r37_feedback/RESULTS.json'),(root/'V12_npu_lab/results/narrow_dense_20260929/REPORT.md','../../../V12_results/2026-09-29_r37_feedback/RESULTS.json')]:
 text=p.read_text(encoding='utf-8')
 if not text.startswith('> Judge 更新：'):
  p.write_text(f'> Judge 更新：r37 全15点Pass，11/12=97.32/116.02μs，未显示收益，不晋升；主线仍为r33。下面保留提交前的实验记录。[结果]({rel})\n\n'+text,encoding='utf-8')

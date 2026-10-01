"""Archive the two r22 Judge screenshots and build one full-guard diagnostic."""
from pathlib import Path
import hashlib,json,shutil

root=Path(__file__).resolve().parents[1]
out=root/'BMMS_V12'; lab=root/'V12_npu_lab'; harness=lab/'harness'
feedback=root/'V12_results/2026-09-28_r22_feedback'
feedback.mkdir(parents=True,exist_ok=True)
def dump(p,obj):
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(data):return hashlib.sha256(data).hexdigest()

runs=[
 [2.38,4.42,5.31,6.39,6.54,14.05,8.89,45.44,69.37,83.68,100.70,124.21,14.77,13.13,11.16],
 [2.24,4.83,5.30,6.28,6.68,14.47,9.66,46.62,70.66,84.20,102.12,124.40,15.17,13.88,11.26]]
best=[1.22,1.58,2.13,2.92,1.89,7.07,3.68,14.88,50.68,72.39,74.82,91.20,5.14,5.40,4.05]
source=(out/'v12_r22_dense_nz_pitch.asc').read_bytes()
dump(feedback/'RESULTS.json',dict(version='v12_r22',
    attribution='Assumed from unique preceding candidate; screenshots contain no source hash or version label',
    source_sha256=sha(source),runs=[dict(run=i+1,all_pass=True,cases=[
        dict(case=j+1,latency_us=t,best_us=best[j],pass_=True,error_pct=0) for j,t in enumerate(row)])
        for i,row in enumerate(runs)],
    decision='No clear Case11/12 benefit; not promoted. Latencies alone do not identify dispatch.'))
for i,name in enumerate(['cac0551a6f9ae52ecc8a12e364f244fd.png','44e27bfeef60efeca386ba23af9d68d2.png']):
    img=Path('E:/Tencent Files/3232896164/nt_qq/nt_data/Pic/2026-09/Ori')/name
    if img.exists():shutil.copyfile(img,feedback/f'judge_{i+1}.png')
(feedback/'ANALYSIS.md').write_text('''# r22 两次 Judge 反馈

按对话中唯一前序候选归属 r22；截图没有版本名或源码哈希，归属属于上下文推定。

两次均 15/15 Pass、误差显示 0.00%。Case11=100.70 / 102.12μs，Case12=124.21 / 124.40μs，未表现出明确收益，r22 不晋升；主线维持 r19。

Case8=45.44 / 46.62μs，Case15=11.16 / 11.26μs。r22 的新增路径不覆盖已知 Case8/15 区域，不能把这两点以及 Case2/7 的单次更快归功于 r22。

当前有两种待区分情况：隐藏输入没有进入 r22，或进入后没有获得合成输入中的收益。耗时接近基线不能证明未命中，更不能据此推断 M/N/K 均为 64 的倍数。

下一步只提交 r23：复制 r22 的 Eligible、Prefer、ValidPlan、调用顺序及 workspace 分配条件，成功后改用原 R06 单组完整计算作为信号。未命中回到 r19。该版本用于诊断，不作为优化候选。
''',encoding='utf-8')

base=(out/'v12_baseline_r19.asc').read_bytes()
assert sha(base)=='27ff91a8e886644ba99b68e3a59ed4d5ed0a001039d6c56074df098d4c66c021'
s=source.decode('utf-8');a=s.index('// BMMS1222_BEGIN');b=s.index('// BMMS1222_END',a)+len('// BMMS1222_END')
module=s[a:b].replace('BMMS1222','BMMS1223').replace('bmms1222','bmms1223')
start=module.index('    auto ap=ws;');end=module.index('    if(aclrtSynchronizeStream',start)
module=module[:start]+'''    // Diagnostic only: same full guard and allocation as r22, then original
    // R06 one-group real computation. This intentionally serializes tile work.
    auto q=StressPlan(p);
    auto ring=ws+bmms1219::ABytes(p)+bmms1219::BBytes(p);
    auto part=ring+bmms11r2::RingBytes(q);
#define BMMS1223_CALL(NAME) NAME<<<q.blocks,nullptr,stream>>>(a,b,y,ring,part,q)
    if(dtype==1){
      if(!ta&&!tb){BMMS1223_CALL(bmms11r2_f16_nn);}else if(!ta&&tb){BMMS1223_CALL(bmms11r2_f16_nt);}
      else if(ta&&!tb){BMMS1223_CALL(bmms11r2_f16_tn);}else{BMMS1223_CALL(bmms11r2_f16_tt);}
    }else{
      if(!ta&&!tb){BMMS1223_CALL(bmms11r2_b16_nn);}else if(!ta&&tb){BMMS1223_CALL(bmms11r2_b16_nt);}
      else if(ta&&!tb){BMMS1223_CALL(bmms11r2_b16_tn);}else{BMMS1223_CALL(bmms11r2_b16_tt);}
    }
#undef BMMS1223_CALL
'''+module[end:]
start=module.index('static inline bool TryLaunch')
module=module[:start]+'''static inline bmms11r2::Plan StressPlan(const Plan& p){
    auto q=p.cube;q.pM=1;q.pN=1;q.tasks=q.B;q.blocks=1;return q;
}
'''+module[start:]
module=('\n'+module+'\n\n').encode('utf-8')
idx=base.index(b'extern "C" void run_kernel');result=base[:idx]+module+base[idx:]
hook=b'    if(bmms1223::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
idx=result.index(b'    if(bmms11r2::TryLaunch(a,b,y,');result=result[:idx]+hook+result[idx:]
assert result.replace(module,b'',1).replace(hook,b'',1)==base
filename='v12_r23_probe_r22_coverage.asc'
(out/filename).write_bytes(result);(harness/'r23.asc').write_bytes(result)
manifest=dict(version='v12_r23',file=filename,sha256=sha(result),parent='v12_baseline_r19.asc',
    parent_sha256=sha(base),kind='diagnostic_only',status='validation pending',
    predicate_source='v12_r22_dense_nz_pitch.asc',predicate_source_sha256=sha(source),
    parent_exactly_recoverable=True,workspace_allocation_matches_r22=True,
    signal='original R06 pM=pN=tasks=blocks=1 after exact r22 guard and successful allocation',
    limitations=['Negative cannot distinguish metadata/predicate rejection from allocation failure.',
                'Source attribution of r22 screenshots is inferred from conversation.',
                'No artificial delay; stress computes the full mathematical output.'])
dump(out/'v12_r23_manifest.json',manifest)
cm=harness/'CMakeLists.txt';t=cm.read_text(encoding='utf-8')
if 'add_executable(bench_r23 ' not in t:
    t+='''
add_executable(bench_r23 main.asc)
target_compile_definitions(bench_r23 PRIVATE BMMS_KERNEL_HEADER="r23.asc" BMMS_VARIANT="r23")
target_link_libraries(bench_r23 PRIVATE tiling_api register platform unified_dlog dl m graph_base)
target_include_directories(bench_r23 PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_options(bench_r23 PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=${NPU_ARCH}>)
'''
cm.write_text(t,encoding='utf-8',newline='\n')
main=json.loads((out/'MAINLINE.json').read_text(encoding='utf-8'))
assert main['accepted_version']=='v12_r19'
for c in main['candidates']:
    if c['version']=='v12_r22':c.update(status='Judge two runs all15 Pass; no clear Case11/12 benefit; not promoted',judge_feedback='../V12_results/2026-09-28_r22_feedback/RESULTS.json')
main.update(recommended_candidate=None,next_action='Validate single r23 full-r22-guard coverage diagnostic; preserve r19')
dump(out/'MAINLINE.json',main)
p=out/'v12_r22_manifest.json';m=json.loads(p.read_text(encoding='utf-8'));m.update(status='Judge two runs all15 Pass; no clear Case11/12 benefit; not promoted',judge_feedback='../V12_results/2026-09-28_r22_feedback/RESULTS.json');dump(p,m)
p=out/'v12_r22_README.md';t=p.read_text(encoding='utf-8');notice='> Judge 两次 15/15 Pass，但 11/12 无明确收益；不晋升。主线仍为 r19。以下为提交前记录。\n\n'
if not t.startswith(notice):p.write_text(notice+t,encoding='utf-8')
print(filename,manifest['sha256'])

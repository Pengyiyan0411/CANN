"""Record r23's negative result; invert only the r22 physical-pitch predicate."""
from pathlib import Path
import hashlib,json,shutil
r=Path(__file__).resolve().parents[1];o=r/'BMMS_V12';lab=r/'V12_npu_lab';h=lab/'harness'
f=r/'V12_results/2026-09-28_r23_feedback';f.mkdir(exist_ok=True,parents=True)
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(b):return hashlib.sha256(b).hexdigest()
times=[2.36,4.75,5.24,6.48,6.52,14.49,9.53,46.30,69.69,84.10,101.79,123.57,15.06,13.41,10.84]
best=[1.22,1.58,2.13,2.92,1.89,7.07,3.68,14.88,50.68,72.39,74.82,91.20,5.14,5.40,4.05]
s23=(o/'v12_r23_probe_r22_coverage.asc').read_bytes()
dump(f/'RESULTS.json',dict(version='v12_r23',attribution='Inferred from preceding unique diagnostic; screenshot has no source/version label',source_sha256=sha(s23),
    all_pass=True,cases=[dict(case=i+1,latency_us=t,best_us=best[i],pass_=True,error_pct=0) for i,t in enumerate(times)],
    decode={'11':'NO strong stress signal','12':'NO strong stress signal'},
    interpretation='This run did not show the calibrated complete-r22-guard stress channel. Prefer=false is plausible but not proved; retain other-guard/allocation/source-attribution alternatives.'))
img=Path('E:/Tencent Files/3232896164/nt_qq/nt_data/Pic/2026-09/Ori/bbc3b38babdce1a82784efb524e0a90b.png')
assert img.exists();shutil.copyfile(img,f/'judge.png')
(f/'ANALYSIS.md').write_text('''# r23 Judge：11/12 均无压力信号

截图按唯一前序诊断归属 r23；未获得平台源码哈希。15/15 Pass，显示误差均 0.00%。11=101.79μs，12=123.57μs，均处在正常通道；与此前校准的约 1.16ms / 1.50ms 单组压力通道明显不同。

因此本次不支持进入 r22 的完整分支。r22 持平不能当作 NZ 在这两个输入上的负面性能实验，因为执行路径尚未确认。主线仍 r19；r23 是诊断，不晋升。

源码守卫拆分：公开 ABI 限制 dtype 为 FP16/BF16；队友探针对 B/M/N/K 与 R06 对齐给出了范围约束；r22 额外的关键筛选是 `(ta && M%64!=0) || ((tb ? K : N)%64!=0)`。最可能为该筛选不成立，但还不能排除范围假设不符、ValidPlan/资源分配失败或源码归属问题。

下一版 r24 仅将 Prefer 条件取反，Eligible / ValidPlan / malloc 大小和调用位置全部保持，命中后仍用原 R06 单组计算。这样一次提交即可同时获得两点的正证据。

若 r24 命中：确认该点本次满足范围/计划/分配条件且 Prefer=false；从而明确 r22 的分派门槛排除了这类输入。可推出 `(!ta || M%64==0) && ((tb?K:N)%64==0)`，不能推出 M/N/K 全都为 64 的倍数。

若 r24 仍无信号：暂不做对齐假设，也不直接去掉 r22 的门槛。复核测评源码、前序路由、形状范围和分配条件。原本不加门槛的本地 NZ 筛选曾出现最差 29.99% 退化，因此不能用扩大覆盖代替性能验证。

若确认对齐，后续在该输入族测试原 R06 的任务划分、宏块及 L1 搬运复用；r22 非对齐 NZ 路线暂停。11/12 各自判读，无需先精确全部 M/N/K。
''',encoding='utf-8')

new=s23.replace(b'BMMS1223',b'BMMS1224').replace(b'bmms1223',b'bmms1224')
condition=b'if(!Eligible(B,M,N,K,dtype,cores)||!Prefer(M,N,K,ta,tb))return false;'
assert new.count(condition)==1
new=new.replace(condition,b'if(!Eligible(B,M,N,K,dtype,cores)||Prefer(M,N,K,ta,tb))return false;',1)
oldcomment=b'// Diagnostic only: same full guard and allocation as r22, then original'
assert new.count(oldcomment)==1
new=new.replace(oldcomment,b'// Diagnostic only: complement of r22 Prefer; all other guards and allocation match.\n    // Execute the original',1)
base=(o/'v12_baseline_r19.asc').read_bytes()
a=new.index(b'\n// BMMS1224_BEGIN');b=new.index(b'// BMMS1224_END',a)+len(b'// BMMS1224_END\n\n')
hook=b'    if(bmms1224::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
assert (new[:a]+new[b:]).replace(hook,b'',1)==base
filename='v12_r24_probe_r22_complement.asc'
(o/filename).write_bytes(new);(h/'r24.asc').write_bytes(new)
dump(o/'v12_r24_manifest.json',dict(version='v12_r24',file=filename,sha256=sha(new),parent='v12_baseline_r19.asc',parent_sha256=sha(base),
    kind='diagnostic_only',status='validation pending',predicate='Eligible && !Prefer && ValidPlan && same workspace allocation success',
    purpose='Positive confirmation of whether physical pitch guard excludes Case11/12',r23_feedback='../V12_results/2026-09-28_r23_feedback/RESULTS.json',
    device_code_unchanged=True,parent_byte_recovery=True))
cm=h/'CMakeLists.txt';t=cm.read_text(encoding='utf-8')
if 'add_executable(bench_r24 ' not in t:
    start=t.index('add_executable(bench_r23 ');t+='\n'+t[start:].replace('r23','r24')
cm.write_text(t,encoding='utf-8',newline='\n')
for name in ['check_r23.sh','archive_r23.py']:
    t=(h/name).read_text(encoding='utf-8').replace('r23','r24').replace('R23','R24')
    if name.endswith('.sh'):t=t.replace('ids={0,6,8,13,24,34,41,54}','ids={0,1,2,3,6,8,13,24,27,34,41,54}')
    else:t=t.replace("if p.is_file()}","if p.is_file() and p.suffix != '.zip'}")
    (h/name.replace('r23','r24')).write_text(t,encoding='utf-8',newline='\n')
t=(lab/'validate_r23_host.py').read_text(encoding='utf-8').replace('r23','r24').replace('1223','1224').replace('v12_r24_probe_r22_coverage','v12_r24_probe_r22_complement')
t=t.replace("b=section(new,'    if(!Eligible(B,M,N,K,dtype,cores)||!Prefer','    // Diagnostic only:')", "b=section(new,'    if(!Eligible(B,M,N,K,dtype,cores)||Prefer','    // Diagnostic only:')")
t=t.replace("assert a.replace('bmms1222','bmms1224')==b\nbase=", "assert a.replace('bmms1222','bmms1224').replace('||!Prefer','||Prefer')==b\nbase=")
t=t.replace('if(!pref||!bmms1224::ValidPlan(p,cores))continue;','if(pref||!bmms1224::ValidPlan(p,cores))continue;')
t=t.replace('guards_text_identical=True','guard_functions_identical=True,only_prefer_negated=True')
(lab/'validate_r24_host.py').write_text(t,encoding='utf-8')
main=json.loads((o/'MAINLINE.json').read_text(encoding='utf-8'));assert main['accepted_version']=='v12_r19'
main['active_diagnostic'].update(status='Judge all15 Pass; Case11 101.79us and Case12 123.57us: no stress signal',feedback='../V12_results/2026-09-28_r23_feedback/RESULTS.json')
main.update(recommended_candidate=None,next_action='Validate r24 complement probe; r19 remains accepted');dump(o/'MAINLINE.json',main)
p=o/'v12_r23_manifest.json';m=json.loads(p.read_text(encoding='utf-8'));m.update(status='Judge all15 Pass; Case11/12 both no stress signal',feedback='../V12_results/2026-09-28_r23_feedback/RESULTS.json');dump(p,m)
p=o/'v12_r23_README.md';t=p.read_text(encoding='utf-8');notice='> Judge：15/15 Pass，11=101.79μs、12=123.57μs，均无压力信号。后续使用 r24 互补条件确认；以下为提交前说明。\n\n'
if not t.startswith(notice):p.write_text(notice+t,encoding='utf-8')
print(filename,sha(new))

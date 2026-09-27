"""Resume original D24 probes byte-for-byte and retain frozen R25 separately."""
from pathlib import Path
import argparse,csv,hashlib,importlib.util,json,shutil,subprocess,zipfile
ROOT=Path(__file__).resolve().parents[1];HERE=Path(__file__).resolve().parent
ORIGINAL=ROOT/'BMMS_V11_D24_Diagnostics';OUT=ROOT/'BMMS_V11_D24_Resume'
RESULT=ROOT/'V11_results/2026-09-27_r27_observed'
PREVIOUS='9d289958c60e7df38df2cbbf808c23984e91a670'
R25_SHA='7defd06457ddb0e356cbf4cc8407f31cbb7c622acf6efd66070be212fa4eacb2'
DATA=[2.46,5.47,5.24,6.50,6.90,15.15,11.53,92.97,71.24,85.68,101.69,124.17,17.77,14.24,15.12]
BEST=[1.22,1.58,2.16,2.92,1.89,7.09,3.69,14.88,51.77,72.47,74.82,91.20,5.19,5.40,4.05]
FIRST=['C01_R03_1G','R7_01_M_LT128','R7_02_N_LT256','R7_03_MACRO_OCC_LT_CORES','R7_04_K_GE512','R7_05_K_GE1024','L00_K1_CONTROL','L05_SPATIAL_EQ1']
CONDITIONAL=['L01_B_EQ1','L02_M_LE64','L03_N_LE128','L04_MN_LE4096','L06_SPLITS_GE8','C00_NATIVE_1G','X6_01_MACRO_1G','X6_02_TREE_1W','X6_03_FALLBACK_1CORE']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,s):p.write_text(s,encoding='utf-8',newline='\n')
def dump(p,d):write(p,json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def record(image):
    RESULT.mkdir(exist_ok=True);dst=RESULT/'observation_01.png'
    if not dst.exists():assert image,'first archive requires --image';shutil.copyfile(image,dst)
    if image:assert sha(dst)==sha(image)
    src=ROOT/'BMMS_V11_R27/R27_DENSE_UNITFLAG.asc'
    dump(RESULT/'RESULT.json',dict(date='2026-09-27',working_attribution='R27_DENSE_UNITFLAG',
        attribution_basis='latest delivered candidate; user reports no benefit and explicitly asks to retain R25 and resume D24',
        user_explicit_filename_confirmation=False,platform_source_hash_verified=False,
        archived_source=src.relative_to(ROOT).as_posix(),archived_source_sha256=sha(src),
        screenshot=dst.name,screenshot_sha256=sha(dst),pass_count=15,displayed_error_pct=[0.0]*15,
        us=DATA,best_column_us=BEST,decision='R27 not promoted; R25 retained; return to original D24 diagnostic probes',
        new_performance_candidate_requested=False,performance_root_cause_confirmed=False,
        statistical_significance_claimed=False,Case5_regression_excluded=False))
    with (RESULT/'measurements.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.writer(f);w.writerow(['case','status','displayed_error_pct','time_us','best_column_us'])
        for i,t in enumerate(DATA,1):w.writerow([i,'Pass','0.00',f'{t:.2f}',f'{BEST[i-1]:.2f}'])
    write(RESULT/'AUDIT.md','''# R27回传：不合入，保留R25，回到D24诊断

最新图按交付上下文归属R27，用户没有重述文件名或平台源码hash；15/15 Pass、误差栏均0.00%。
用户明确表示“没用。保留R25的成果，回到D24_diagnose，我准备完成剩下的探针”。本轮据此停止内核优化。

| Case | R25两次 μs | R26 μs | 本次R27 μs |
|---|---:|---:|---:|
| 5 | 6.60 / 6.45 | 6.86 | 6.90 |
| 13 | 16.80 / 16.91 | 17.26 | 17.77 |
| 14 | 13.84 / 13.63 | 13.77 | 14.24 |
| 15 | 15.30 / 15.03 | 15.43 | 15.12 |

R27对目标13/14没有收益证据，不升级。Case5新读数高于此前两次，不能直接归为噪声，也不据单次判定根因。
不跨点缩放、不拼接最低值，不用动态最优列计算本轮算法收益。
这次结果不证明UnitFlag没有执行，也不证明13/14已达到硬件下限。

R25源码与提交包保留原字节。D24也保留原R23诊断基线；后续shape解码以D24同基线控制为准。
N01–N05已有全部回传，无需重跑；恢复Case7 R7组、Case15 L组，Case6随完整截图观察。
''')

def prepare():
    d24=load('d24_resume_verify',ROOT/'V11_diagnostics24/build.py');composition=d24.verify()
    r25=load('r25_resume_verify',ROOT/'V11_native_targeted25/build.py');r25proof=r25.verify()
    base=ROOT/'BMMS_V11_R25/R25_NATIVE_TARGETED.asc';assert sha(base)==R25_SHA
    manifest=json.loads((ORIGINAL/'MANIFEST.json').read_text(encoding='utf-8'))
    entries={x['file']:x for x in manifest['probes']+manifest['controls']}
    for name,item in entries.items():assert sha(ORIGINAL/name)==item['sha256'],name
    completed={x['probe'] for x in json.loads((ROOT/'V11_results/2026-09-27_d24_native/RESULT.json').read_text(encoding='utf-8'))['submissions']}
    assert completed=={'N01_K_EQ32','N02_K_EQ64','N03_M_LE32','N04_N_LE32','N05_B_EQ1'}
    (OUT/'D24').mkdir(parents=True,exist_ok=True);(OUT/'KEEP_R25').mkdir(exist_ok=True)
    (OUT/'ORIGINAL_CHECKS').mkdir(exist_ok=True)
    files=[]
    for name,item in entries.items():
        if Path(name).stem in completed:continue
        dst=OUT/'D24'/name;shutil.copyfile(ORIGINAL/name,dst);assert sha(dst)==item['sha256']
        files.append(dict(path=dst.relative_to(OUT).as_posix(),original=(ORIGINAL/name).relative_to(ROOT).as_posix(),sha256=sha(dst)))
    assert len(files)==18
    dst=OUT/'KEEP_R25/R25_NATIVE_TARGETED.asc';shutil.copyfile(base,dst);assert sha(dst)==R25_SHA
    files.append(dict(path=dst.relative_to(OUT).as_posix(),original=base.relative_to(ROOT).as_posix(),sha256=sha(dst)))
    for name in ['MANIFEST.json','CPU_CHECKS.json','HOST_CHECKS.json']:
        src=ORIGINAL/name;dst=OUT/'ORIGINAL_CHECKS'/name;shutil.copyfile(src,dst)
        files.append(dict(path=dst.relative_to(OUT).as_posix(),original=src.relative_to(ROOT).as_posix(),sha256=sha(dst)))
    dump(OUT/'MANIFEST.json',dict(purpose='original D24 remaining probes, not new kernels or a rebase to R25',
        performance_baseline='KEEP_R25/R25_NATIVE_TARGETED.asc',diagnostic_baseline='D24/CONTROL_R23.asc',
        completed_N_probes=sorted(completed),remaining_results='not received in this conversation; not a claim they have never run',
        recommended_first_batch=FIRST,conditional_followups=CONDITIONAL,files=files,
        D24_composition=composition,R25_composition=r25proof,new_CANN_compile_or_NPU_test=False))
    with (OUT/'RESULT_TEMPLATE.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['probe_file','case','status','time_us','displayed_error_pct','screenshot_or_notes'])
        for name in ['CONTROL_R23']+FIRST+CONDITIONAL:
            for c in range(1,16):w.writerow([name+'.asc',c,'','','',''])
    write(OUT/'README.md','''# 回到D24：R25成果冻结，完成剩余诊断

本包是原D24文件的原字节续跑集合，不是新版本内核，也没有把探针移植到R25。
R26/R27没有显示13/14收益，均不合入。`KEEP_R25/R25_NATIVE_TARGETED.asc`保存已取得的R25成果。

**两条基线必须分清：** 冲榜保留R25；D24诊断仍以`D24/CONTROL_R23.asc`为控制。
D24版本中Case5回到旧耗时属于基线差异，不表示R25成果丢失；不要据此判断新探针伤到了Case5。
R25未改动R03、Split-K和其他早期路由，因此可继续原D24的Case7/15诊断，不需要重新编号。

## 已完成

N01–N05全部已回传，每份15/15 Pass，不需要重跑。当前工作结论：

- Case5：Native，K128，M/N∈{16,32}，B>1。
- Case13/14：Native，K128，B1，M/N≥48且16对齐。
- Case6仍未定位；Case7和Case15的剩余几何信息等待R7/L组。

已完成的N探针没有放入续跑文件夹，原D24完整包和结果归档保持不变。

## 先提交这一组

每个`.asc`都是独立完整提交，保留完整15点结果并注明文件名。

| 顺序 | D24目录中的文件 | 重点观察 |
|---|---|---|
| 1 | C01_R03_1G.asc | 当前R23基线上Case7的无条件R03压力对照，同时观察6 |
| 2 | R7_01_M_LT128.asc | Case7：M<128 |
| 3 | R7_02_N_LT256.asc | Case7：N<256 |
| 4 | R7_03_MACRO_OCC_LT_CORES.asc | Case7：宏块任务数是否不足核组数 |
| 5 | R7_04_K_GE512.asc | Case7：K≥512 |
| 6 | R7_05_K_GE1024.asc | Case7：K≥1024 |
| 7 | L00_K1_CONTROL.asc | Case15：当前Split-K降为单K分片后的实际耗时 |
| 8 | L05_SPATIAL_EQ1.asc | Case15：是否只有一个空间任务 |

C01是D24原有阳性对照，不是旧C512/C1024阈值探针。已有本包C01有效结果时可以直接用它，避免重复提交。
CONTROL_R23用于需要相邻正常控制时。C01若不能形成明确压力响应，暂停对R7阴性作shape解码。
L00先标定真实单分片耗时，不预设它就是历史R14的37 μs。

## 再按结果展开

- L05若可靠阳性：一次确认B1、M≤64、N≤128，L01/L02/L03可跳过。
- L05若可靠阴性：用L01_B_EQ1、L02_M_LE64、L03_N_LE128分别拆开条件。
- L04_MN_LE4096判断输出平面大小；L06_SPLITS_GE8判断原分片数，可在L00信号有效后继续。
- Case6先借用上述完整截图判断响应。仍未知时，用C00_NATIVE_1G检查Native，
  再按需用X6_01_MACRO_1G、X6_02_TREE_1W、X6_03_FALLBACK_1CORE定位剩余路径。
  C00对已标定的5/13/14无需重跑，仅在Case6等未定位目标需要时使用。

## 解码原则

先看Pass。明显离开正常控制波动、并接近同路径压力对照，才记阳性；阴性需要有效阳性对照。
小幅变化记不确定；TLE、编译失败、精度失败不能当作shape位。历史11→33 μs只是先验线索，不是硬阈值。
R7_04/05可靠结果：否/否→256≤K<512；是/否→512≤K<1024；是/是→K≥1024；否/是需排查。
`macro_occ`不是实测硬件占用率。L05只解释原空间任务数，不等于启用Split-K后的launch核组数。
全无响应不能排除所有路径，原计划可能本来就接近单组。

## 文件核验

18份剩余D24源文件与原D24逐字一致，R25副本也与冻结版逐字一致，SHA256见MANIFEST.json。
ORIGINAL_CHECKS保存原D24检查报告；本次仅核对身份和重新打包，没有重跑设备或性能测试。
RESULT_TEMPLATE.csv是可选记录表，所有结果栏留空；直接反馈带文件名的完整截图也可以。
''')
    return composition,r25proof,files

def documents():
    snapshot=ROOT/'audit_current/AUDIT_R27_DELIVERY.md'
    old=subprocess.check_output(['git','show',PREVIOUS+':BMMS/BatchMatmulMaxSum_当前审计报告_2026-09-26.md'],cwd=ROOT/'CANN_archive')
    if snapshot.exists():assert snapshot.read_bytes()==old
    else:snapshot.write_bytes(old)
    text='''# BatchMatmulMaxSum：保留R25，回到D24诊断

用户最新决定：R27无收益，保留R25成果，完成剩下的D24探针。本轮不交付新的优化内核。
最新图15/15 Pass，Case5/13/14为6.90/17.77/14.24 μs；按交付上下文归属R27，平台源码hash未核验。
R26、R27均不作为升级。所有旧源码和提交包保持冻结。

- [R25保留版](BMMS_V11_R25/R25_NATIVE_TARGETED.asc)
- [D24续跑包](BMMS_V11_D24_续跑包.zip)
- [续跑顺序及解码说明](BMMS_V11_D24_Resume/README.md)
- [原D24完整包](BMMS_V11_D24_诊断包.zip)
- [N01–N05已完成结果](V11_results/2026-09-27_d24_native/AUDIT.md)
- [R27最新否定结果](V11_results/2026-09-27_r27_observed/AUDIT.md)
- [当前审计](BatchMatmulMaxSum_当前审计报告_2026-09-26.md)

冲榜基线R25与诊断基线R23分开保留。D24内Case5回到旧耗时不代表R25成果丢失。
N01–N05无需重跑。先C01→R7_01–05，再L00→L05；剩余L和Case6按结果展开。
原D24代码未改，续跑包仅重组已有文件；没有新增CANN/NPU或性能验证。
'''
    write(ROOT/'README.md',text)
    github=text
    for prefix in ['BMMS_V11_R25/','BMMS_V11_D24_','V11_results/','BatchMatmulMaxSum_当前审计报告_2026-09-26.md']:
        github=github.replace(']('+prefix,'](BMMS/'+prefix)
    write(HERE/'CANN_README.md',github)
    write(ROOT/'BatchMatmulMaxSum_当前审计报告_2026-09-26.md','''# 当前审计：停止R26/R27升级，保留R25并恢复D24

2026-09-27。用户明确要求保留R25、回到D24_diagnose，完成剩余探针。
本轮停止13/14内核试改，不交付R28或重命名优化版本。

| Case | R25两次 μs | R26 μs | 最新R27 μs |
|---|---:|---:|---:|
| 5 | 6.60 / 6.45 | 6.86 | 6.90 |
| 13 | 16.80 / 16.91 | 17.26 | 17.77 |
| 14 | 13.84 / 13.63 | 13.77 | 14.24 |
| 15 | 15.30 / 15.03 | 15.43 | 15.12 |

新图15/15 Pass、误差栏均0.00%，按交付上下文归R27，文件名及平台源码hash没有独立确认。
R26/R27均无13/14收益证据，不合入。Case5上涨不自动解释成波动；暂不作根因或统计显著性判断。
完整原图与15点读数在[结果归档](V11_results/2026-09-27_r27_observed/AUDIT.md)。

## 保留成果与诊断基线

R25冲榜源码SHA256为`7defd06457ddb0e356cbf4cc8407f31cbb7c622acf6efd66070be212fa4eacb2`。
原R25源码、ZIP以及R26/R27历史文件全部保留原字节；续跑包另存R25副本用于清楚区分用途。
D24仍以原R23为诊断基线，不能用R25 Native耗时直接判断D24探针的5/13/14是否命中。
R25的改动仅在Native消费者，R03、Split-K等原路由逐字保留，因此可以继续原D24。

## 当前探针进度

N01–N05已收齐，全部15/15，不重跑。工作结论保持：

- 5：Native K128，M/N∈{16,32}，B>1。
- 13/14：Native K128，B1，M/N≥48且16对齐。
- 6：路径未知，N条件阴性不能排除Native。
- 7：R03 residual工作判断，继续用有效单组压力信号解码；不恢复旧K<512推断。
- 15：已获Split-K收益，旧M16..112/N16..240/K4096..8192证据保留，B和空间任务待L组。

先跑C01_R03_1G和R7_01–05，再L00_K1_CONTROL→L05_SPATIAL_EQ1。
L05可靠阳性同时确认B1/M≤64/N≤128，L01–03可跳过；否则拆开验证。
L04/L06按信息需要追加。Case6先复用完整截图，仍未知再用C00和X6组。
这些剩余文件未收到本包同名回传，不等于断言用户从未提交过；已有结果可直接衔接。

## 交付与检查

[D24续跑包](BMMS_V11_D24_续跑包.zip)包含18份原字节D24文件、原字节R25副本、原检查报告和空白记录表。
可逆host修改检查及所有原文件SHA256重新核对通过；没有修改设备代码，没有新增CANN/NPU测试。
旧D24模型和host结果作为原历史证据保留，不包装成这轮新执行的测试。
[提交顺序](BMMS_V11_D24_Resume/README.md)明确正常控制、阳性压力控制及按结果展开的条件。
TLE/编译失败/精度失败或小幅起伏不能当shape位；不跨case缩放、不拼最低值。

R27交付时的报告保存为[原样快照](audit_current/AUDIT_R27_DELIVERY.md)。
''')

def package(composition,r25proof,sourcefiles):
    archive=ROOT/'BMMS_V11_D24_续跑包.zip';files=sorted(p for p in OUT.rglob('*') if p.is_file())
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in files:
            info=zipfile.ZipInfo(OUT.name+'/'+p.relative_to(OUT).as_posix(),date_time=(2026,9,27,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,p.read_bytes())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and len(z.namelist())==len(files)
        for p in files:assert z.read(OUT.name+'/'+p.relative_to(OUT).as_posix())==p.read_bytes()
    for row in sourcefiles:assert sha(OUT/row['path'])==sha(ROOT/row['original'])==row['sha256']
    checks=dict(d24_remaining_sources=18,R25_frozen_copy=True,all_sources_byte_identical_to_original=True,
        D24_composition=composition,R25_composition=r25proof,N01_to_N05_already_received=True,
        package=archive.name,package_sha256=sha(archive),package_bytes=archive.stat().st_size,zip_members=len(files),
        zip_roundtrip_verified=True,new_device_code=False,new_CANN_compile=False,new_NPU_run=False,
        script_sha256=sha(Path(__file__)))
    dump(HERE/'RESUME_CHECKS.json',checks);print(json.dumps(checks,ensure_ascii=True))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--image',type=Path);args=ap.parse_args()
    record(args.image);composition,r25proof,files=prepare();documents();package(composition,r25proof,files)
if __name__=='__main__':main()

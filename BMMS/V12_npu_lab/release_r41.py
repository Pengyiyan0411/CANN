from pathlib import Path
import json,hashlib,zipfile,statistics,collections,shutil
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V12';out=root/'V12_npu_lab/results/plan_equal_20260929'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
with zipfile.ZipFile(out/'r41_evidence.zip') as z:
 assert z.testzip() is None
 hashes=json.loads(z.read('manifest.json'))['files']
 assert all(hashlib.sha256(z.read(p)).hexdigest()==h for p,h in hashes.items())
 assert all(not Path(p).is_absolute() and '..' not in Path(p).parts for p in z.namelist())
 z.extractall(out/'evidence')
e=out/'evidence';source=v/'v12_r41_dense_flat_macro.asc';digest=sha(source)
assert source.read_bytes()==(e/'r41.asc').read_bytes()
assert (v/'v12_baseline_r33.asc').read_bytes()==(e/'r33.asc').read_bytes()
assert sha(v/'v12_baseline_r33.asc')=='86debd5c403af4bb436d6c042de4530faf05637cf6fd1aeaae6ed6b410d11d80'
validation=read(e/'results/r41_validation_summary.json');assert validation['all_pass'] and validation['precision_calls']==690
perf={}
for tag in ['discovery','holdout','controls']:
 d=read(e/f'results/r41_{tag}_summary.json');rows=[]
 assert d['source_sha256']['r41']==digest
 for r in d['summary']:
  active=any('bmms1241_' in k for x in d['runs'] if x['case']==r['case'] and x['version']=='r41' for k in x['kernels'])
  rows.append(dict(case=r['case'],active=active,baseline_us=r['baseline_median_us'],candidate_us=r['candidate_median_us'],
   reduction_percent=100*(1-r['candidate_median_us']/r['baseline_median_us']),windows=[100*(1-b/a) for a,b in zip(r['baseline_medians_us'],r['candidate_medians_us'])]))
 groups={}
 for group,rr in [('all',rows),('active',[r for r in rows if r['active']]),('inactive',[r for r in rows if not r['active']])]:
  if rr:groups[group]=dict(count=len(rr),median=statistics.median(r['reduction_percent'] for r in rr),minimum=min(r['reduction_percent'] for r in rr),maximum=max(r['reduction_percent'] for r in rr),both_windows_improve=sum(min(r['windows'])>0 for r in rr))
 perf[tag]=dict(groups=groups,rows=rows)
assert perf['discovery']['groups']['active']['minimum']>0 and perf['holdout']['groups']['active']['minimum']>0
assert 'active' not in perf['controls']['groups']
audit=read(out/'audit_r41.json');coverage=read(out/'conditional_coverage.json')
summary=dict(accepted_baseline='v12_baseline_r33.asc',recommended_candidate=source.name,judge_pending=True,synthetic_not_hidden=True,
 environment=read(e/'results/environment.json'),validation=validation,host_audit=audit,performance=perf,
 conditional_shape_grid_counts_not_probabilities=coverage,evidence_file_hashes_verified=len(hashes))
write(out/'SUMMARY.json',summary)
sweep=[json.loads(s) for s in (e/'results/plan_sweep.jsonl').read_text().splitlines()];by=collections.defaultdict(set)
for r in sweep:by[r['case']].add((r['pM'],r['pN']))
no_alt=sum(len(p)==1 for p in by.values())
hr=perf['holdout']['groups']['active'];dr=perf['discovery']['groups']['active'];san=validation['sanitizer']
selected=[200,236,250,256,262]
sample_table='\n'.join(f"|{'×'.join(map(str,r['case'][2:5]))}|{r['case'][5]} / {r['case'][6]},{r['case'][7]}|{r['baseline_us']:.3f}|{r['candidate_us']:.3f}|{r['reduction_percent']:.2f}%|" for r in perf['holdout']['rows'] if r['case'][0] in selected)
all_table='\n'.join(f"|{tag}|{r['case'][0]}|{'×'.join(map(str,r['case'][2:5]))}|{r['case'][5]} / {r['case'][6]},{r['case'][7]}|{'是' if r['active'] else '否'}|{r['baseline_us']:.3f}|{r['candidate_us']:.3f}|{r['reduction_percent']:.2f}%|" for tag in perf for r in perf[tag]['rows'])
report=f'''# r40反馈与r41宏块展平分配实验

当前正式基线仍为 **r33**。推荐下一次Judge测试 `v12_r41_dense_flat_macro.asc`；r41是性能候选，不是压力探针，尚未晋升。

## 这次探针确认了什么

r40截图全部15点Pass，Case11 **1.11 ms**、Case12 **1.42 ms**，比上一轮正常耗时约慢11.4/12.4倍，属于明确HIT。版本按对交付的直接回复归属，截图不含源码版本/SHA。原图及完整15点数据保存在 `V12_results/2026-09-29_r40_feedback`。

结合r39未命中和r40命中，二者满足r37的完整适用条件和新区间，但r37选择了与r33相同的计划。因此不能再用“新形状范围错误”解释r37无收益，也不能把其离线已切换子集的收益套用到这两个隐藏点。pM/pN的精确值仍然未知。

## 排查与两步实验

1. 保持现有矩形分片，扫描不增加峰值宏块数的pM/pN组合。在36个符合r40条件的已有样本中，{no_alt}个没有任何替代方案；其余的最好收益多在约1%～2%量级，不适合继续小幅调整筛选阈值。每个扫描组合先通过独立精度检查，再运行3个正反顺序计时窗口。
2. r41改变宏块分配方式：对128×256输出宏块按行展平，并给每核分配连续的一段。矩形分片造成的二维取整浪费不再限制负载均衡。每核最大宏块数成为 `ceil(mTiles*nTiles/blocks)`，只有严格小于r33旧计划峰值才启用。

没有增加输入矩阵缓存或更改K累加方式，Cube仍采用r30已经使用的完整宏块MMAD和跨宏块L1预取。改变的部分是每核宏块遍历、AIV局部行最大值保存和分片结果合并。

## 算法与边界

- 每个宏块的所有K片段仍在同一核完整FP32累加；没有对K做跨核Max或提前归约。
- 每个AIV保存它负责的半行结果。未访问的行初始化为负无穷；每个核组把全M行的局部最大值写入自己的独立分片，两名AIV写互不重叠的半行。
- SyncAll后，对各核组的行结果执行Max，最后Sum-M。等价关系是 `max_N(C)=max_group(max_该组列(C))`，不是交换Sum-K与Max-N。
- 所有输出宏块覆盖一次；GM分片在读取前完整写入，workspace按实际blocks分配。新核数由availableCoreNum取得。
- 路由继承r30的dtype、对齐、physical pitch和Family约束，再限制到已确认的两个形状区间及峰值改善条件。1/2/7/8/9/10/13/15等此前收益路径没有替换。删除新模块和入口可逐字节恢复r33。

新增8个设备入口，总入口数由304变为312。不是新增312种算法。

CPU枚举9种核数、27,648个配置，验证完整宏块/元素覆盖、连续分片边界、每个AIV的行索引和workspace大小；全部通过。最大显式UB申请{audit['max_ub_bytes']}字节，检查上限192KiB；此为缓冲区预算检查，不替代设备安全检测。

## 精度与性能

Ascend910_9362，20 Cube，CANN9.0.0，dav-2201。源码完整编译通过。原166配置加新64配置，共 **230配置×3次=690次全部Pass**。新64配置是32个从未参与之前扫描的新形状，每形状FP16/BF16各一个，覆盖四种转置组合。原集合包含零、全负、尺度变化、重复列、域外控制和其他优化路径。

参考是在实际量化输入上的CPU FP64计算，逐输出容差 `1e-4+1e-4*abs(reference)`，每次调用前NaN填充。最大误差/容许误差比{validation['max_tolerance_ratio']:.9f}。额外profiler调用也逐次验证输出。

性能均通过公共入口msprof task-time测量：每版两个独立进程，A/B与B/A顺序，每配置30次、舍弃前5次，每次1个kernel。以两窗口中位数计算耗时降幅，不把host wall time当kernel时间。

|样本集|配置数|实际启用r41|启用子集降幅中位数|启用子集范围|两窗口都改善|
|---|---:|---:|---:|---:|---:|
|已有形状|48|32|{dr['median']:.2f}%|{dr['minimum']:.2f}%～{dr['maximum']:.2f}%|32/32|
|全新形状|64|38|{hr['median']:.2f}%|{hr['minimum']:.2f}%～{hr['maximum']:.2f}%|38/38|
|域外控制|12|0|不适用|绝对变化−0.100～+0.070μs|不计优化收益|

全新集合按所有64配置统计的降幅中位数为{perf['holdout']['groups']['all']['median']:.2f}%；26个未启用配置轻微变慢0.22%～0.97%，不能用局部样本证明系统性退化原因。已有集合的16个未启用配置变化在±0.36%以内。12个域外控制最大变慢是3.04→3.11μs，保留原始值，不把所有差异直接宣布为噪声。

全新样本的部分例子（均为FP16；这些不是比赛点）：

|M×N×K|dtype / ta,tb|r33 μs|r41 μs|耗时下降|
|---|---|---:|---:|---:|
{sample_table}

比赛隐藏点11/12此前正常约97/115μs，平台标杆为74.82/91.20μs；它们和上表构造样本不是同一shape，不能拿来计算三方加速比。r41的Judge时间待用户回测。

## 检查范围与限制

普通完整二进制的memcheck设240秒限时，完成2例FP16/BF16 NT并通过输出核对，第3例TT开始后超时退出124。已产生的日志没有ERROR，有{san['register_warnings']}条FFTS_BASE_ADDR寄存器复位警告。**这不是4例内存检查全通过，也不是全量安全验收。** 未对r41完成插桩race/init检查；基线历史race/init报告也仍未闭环。原始启动日志、超时状态与检测日志全部保留。

第一次memcheck因日志目录0775权限被工具拒绝，换用独立0750目录后实际启动；最初CPU样本生成遇到torch_npu自动加载缺失环境，禁用设备后端自动加载后仅用CPU重新生成成功。这些失败没有当作测试通过。

r41仍可能不覆盖两个隐藏点中的某一个：在20核、r40条件成立的形状网格中，Case11候选789个M/N组合里348个满足展平峰值下降；Case12为1421个中的852个。这些是网格计数，**不是命中概率**，不能保证Judge两点都收益。

本轮没有继续设计形状探针，也没有把r41自动晋升。若Judge出现稳定收益，则合入主线；若某点持平，先检查是否满足展平收益条件，不把局部NPU数据当隐藏点结果。

## 文件与复现

源SHA256：`{digest}`。r33 SHA保持 `86debd5c403af4bb436d6c042de4530faf05637cf6fd1aeaae6ed6b410d11d80`。

`r41_evidence.zip`的102个文件SHA和ZIP CRC已核验；包含实际源码、CMake、数据生成脚本/seed/hash、数值记录、公开入口原始profiler CSV、内存检查日志与二进制SHA。输入大二进制未打包，可通过生成器重建。`SUMMARY.json`保留完整结果，`PERFORMANCE.md`列出全部124个性能配置。源代码与测试使用的副本逐字节一致。

关键结论：r37无收益已经定位为未换计划；矩形分片的同峰值替代组合机会有限；展平宏块在新旧两个样本集的实际启用子集均获得稳定收益，但隐藏覆盖和最终收益仍需Judge确认。
'''
(out/'REPORT.md').write_text(report,encoding='utf-8')
(out/'PERFORMANCE.md').write_text('# r33 → r41全部性能记录\n\n降幅为正表示r41更快；构造样本ID不是比赛case编号。\n\n|集合|ID|M×N×K|dtype / ta,tb|启用|r33 μs|r41 μs|降幅|\n|---|---:|---|---|---|---:|---:|---:|\n'+all_table+'\n',encoding='utf-8')
readme=f'''# v12_r41：宏块展平分配

**性能候选，主线仍为r33。提交 `{source.name}`，不要提交r40压力探针。**

r40反馈确认11/12满足新区间和完整路由条件，但r37没有改变计划。r41把二维矩形分片改为连续展平宏块，在能严格减少最重核宏块数时启用；每宏块仍完整累加K，跨核只合并行最大值再求和。其他形状回退r33。

- 完整编译通过；230配置、690次数值检查全Pass。
- 原48配置中32个启用，耗时下降中位数11.78%，全部两窗口改善。
- 新64配置中38个启用，下降中位数8.39%，范围4.30%～19.00%，全部两窗口改善。
- 12个域外控制绝对变化−0.100～+0.070μs。不能保证隐藏11/12同时满足新门槛，Judge待测。
- 有限memcheck完成2例后在第3例超时，不能称全量通过；历史race/init问题尚未闭环。

新64配置来自32个新形状×两种dtype，不等于64个独立形状。上述是NPU构造样本收益，不能作为隐藏点预测。

新增8个设备入口，合计312；r33源码未变。请回传15点结果，重点看11/12及其余点有无稳定退化。

[完整报告](../V12_npu_lab/results/plan_equal_20260929/REPORT.md) · [全部性能结果](../V12_npu_lab/results/plan_equal_20260929/PERFORMANCE.md)

SHA256：`{digest}`。
'''
(v/'v12_r41_README.md').write_text(readme,encoding='utf-8')
status='Recommended pending Judge; 230x3 precision Pass; independent active subset median latency reduction8.39%; limited memcheck timed out after2completed cases; r33 remains accepted'
manifest=read(v/'v12_r41_manifest.json');assert manifest['sha256']==digest
manifest.update(status=status,report='../V12_npu_lab/results/plan_equal_20260929/REPORT.md',precision_configurations=230,precision_calls=690,holdout=perf['holdout']['groups'],sanitizer=validation['sanitizer']);write(v/'v12_r41_manifest.json',manifest)
main=read(v/'MAINLINE.json');assert main['accepted_version']=='v12_r33'
diagnostic=main.get('active_diagnostic')
if diagnostic and diagnostic['version']=='v12_r40':
 diagnostic['historical']=True
 if not any(x['version']=='v12_r40' for x in main['historical_diagnostics']):main['historical_diagnostics'].append(diagnostic)
 main['active_diagnostic']=None
main['candidates']=[c for c in main['candidates'] if c['version']!='v12_r41']
main['candidates'].append(dict(version='v12_r41',file=source.name,parent='v12_baseline_r33.asc',sha256=digest,status=status,npu_report='../V12_npu_lab/results/plan_equal_20260929/REPORT.md'))
main.update(recommended_candidate=source.name,latest_experiment_report='../V12_npu_lab/results/plan_equal_20260929/REPORT.md',next_action='Submit r41 performance candidate; compare all15 especially11/12; r33 baseline remains unchanged until Judge confirms benefit.')
write(v/'MAINLINE.json',main)
r40sum=read(root/'V12_npu_lab/results/r40_20260929/SUMMARY.json');r40sum.update(judge_feedback=read(root/'V12_results/2026-09-29_r40_feedback/RESULTS.json'),next_candidate='v12_r41');write(root/'V12_npu_lab/results/r40_20260929/SUMMARY.json',r40sum)
for version,name in [('r40','v12_r40_probe_r37_unchanged_in_domain.asc'),('r41',source.name)]:
 with zipfile.ZipFile(v/f'v12_{version}_submission.zip','w',zipfile.ZIP_DEFLATED) as z:
  for p in [v/name,v/f'v12_{version}_README.md',v/f'v12_{version}_manifest.json']:z.write(p,p.name)
 with zipfile.ZipFile(v/f'v12_{version}_submission.zip') as z:assert z.testzip() is None and z.read(name)==(v/name).read_bytes()
repro=out/'local_reproduction';repro.mkdir(exist_ok=True)
for name in ['prepare_plan_sweep.py','prepare_r41.py','audit_r41.py','analyze_r41.py','release_r41.py']:
 shutil.copyfile(root/'V12_npu_lab'/name,repro/name)
write(repro/'manifest.json',{p.name:sha(p) for p in repro.glob('*.py')})
print(json.dumps(dict(candidate=source.name,sha256=digest,baseline='r33 unchanged',precision=230,holdout=hr,sanitizer=validation['sanitizer'],evidence_files=len(hashes))))

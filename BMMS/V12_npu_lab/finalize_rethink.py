from pathlib import Path
import csv,hashlib,json,statistics as st,tarfile
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V12';out=root/'V12_npu_lab/results/rethink_20261001'
archive=out/'rethink_evidence.tar.gz';e=out/'evidence';e.mkdir(exist_ok=True)
with tarfile.open(archive) as t:
 for member in t.getmembers():
  target=(e/member.name).resolve()
  assert target.is_relative_to(e.resolve()) and not member.issym() and not member.islnk(),member.name
 t.extractall(e,filter='data')
manifest=json.loads((e/'evidence_manifest.json').read_text())
for item in manifest:
 p=e/item['path'];assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256'],p
def load(name):return json.loads((e/'results'/name).read_text())
def lines(name):return [json.loads(s) for s in (e/'results'/name).read_text().splitlines()]
summary={};table=[]
for version in ('r65','r66','r67'):
 d=load(version+'_first8_summary.json');prec=lines(version+'_precision.jsonl')+lines(version+'_extra_precision.jsonl')
 assert len(prec)==186 and all(x['pass'] for x in prec)
 gains=[100*(1-x['candidate_median_us']/x['baseline_median_us']) for x in d['summary']]
 stats=dict(configurations=len(prec),calls=sum(x['repeats'] for x in prec),all_pass=True,
            max_tolerance_ratio=max(x['max_tolerance_ratio'] for x in prec),
            max_abs_error=max(x['max_abs_error'] for x in prec),median_reduction_pct=st.median(gains),
            min_reduction_pct=min(gains),max_reduction_pct=max(gains),
            both_windows_faster=sum(all(a>b for a,b in zip(x['baseline_medians_us'],x['candidate_medians_us'])) for x in d['summary']))
 assert stats['median_reduction_pct']<5,'Candidate merits extended validation: do not reject automatically'
 summary[version]=stats
 for x,gain in zip(d['summary'],gains):
  table.append(dict(version=version,N=x['case'][3],TA=x['case'][6],baseline_us=x['baseline_median_us'],candidate_us=x['candidate_median_us'],reduction_pct=gain))
 for run in d['runs']:
  if run['version']==version:assert all('bmms12'+version[1:]+'_' in name for name in run['kernels'])
 (out/(version+'_first8_summary.json')).write_text(json.dumps(d,indent=2)+'\n')
names={'r65':'case12_unitflag','r66':'case12_transposed_product','r67':'case12_n_order_skew'}
descriptions={'r65':'UnitFlag 交接 L0C；原 K 顺序、分核和归约不变',
              'r66':'直接计算 BᵀAᵀ；256×128 矩阵乘与列最大值，保留原输出行 ownership',
              'r67':'按 M 分片编号旋转 N 宏块遍历起点；保持每个点积的 K 累加顺序'}
for version in names:
 p=v/f'v12_{version}_manifest.json';meta=json.loads(p.read_text())
 src=v/f'v12_{version}_{names[version]}.asc';assert hashlib.sha256(src.read_bytes()).hexdigest()==meta['sha256']
 meta.update(status='CANN build and 186-configuration precision passed; research only, no Judge submission or promotion',
             validation=summary[version],report='../V12_npu_lab/results/rethink_20261001/REPORT.md',
             independent_performance_holdout=False,new_sanitizer_run=False,judge15=False)
 p.write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
 text=f'''# v12_{version}：实验分支

{descriptions[version]}。直接基于 r41，删除新增模块和唯一入口后可逐字节恢复基线。

实卡186配置、602次精度调用全部通过（另有短测和性能运行内检查）。8配置串行ABBA初筛，中位耗时下降 {summary[version]['median_reduction_pct']:.2f}%，范围 {summary[version]['min_reduction_pct']:.2f}%～{summary[version]['max_reduction_pct']:.2f}%。正数表示更快。

不晋升，不建议本轮 Judge15。未运行独立性能留出及新 sanitizer；不能将合成数据当成隐藏 Case12 的收益。

完整实现：[{src.name}]({src.name})；[详细报告](../V12_npu_lab/results/rethink_20261001/REPORT.md)。
'''
 (v/f'v12_{version}_README.md').write_text(text,encoding='utf-8')
diag={}
for variant in ('native','cat0','cat1','fullcat1','pre0'):
 p=lines(variant+'_precision.jsonl');assert len(p)==148 and all(x['pass'] for x in p)
 diag[variant]=dict(configurations=148,calls=sum(x['repeats'] for x in p),all_pass=True,
                    max_y_tolerance_ratio=max(x['y_tolerance_ratio'] for x in p),
                    max_sample_dot_tolerance_ratio=max(x['dot_tolerance_ratio'] for x in p))
failed=lines('pre1_precision.jsonl');assert len(failed)==145 and not failed[-1]['pass'] and failed[-1]['case']==1144
diag['pre1']=dict(configurations_attempted=len(failed),first_failed_case=1144,
                 failed=failed[-1],reason='K shuffle fails full max/sum cancellation check; performance not measured')
summary['diagnostics']=diag
summary['archive']=dict(files=len(manifest),size=archive.stat().st_size,sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
with (out/'PERFORMANCE.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=table[0].keys());w.writeheader();w.writerows(table)
(out/'SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
perf='\n'.join(f"|{x['version']}|{x['N']}|{x['TA']}|{x['baseline_us']:.3f}|{x['candidate_us']:.3f}|{x['reduction_pct']:+.2f}%|" for x in table)
short='\n'.join(f"|{k}|{descriptions[k]}|{summary[k]['median_reduction_pct']:+.2f}%|{summary[k]['min_reduction_pct']:+.2f}%～{summary[k]['max_reduction_pct']:+.2f}%|{summary[k]['both_windows_faster']}/8|" for k in names)
gemm=load('gemm_audit.json')
gt='\n'.join(f"|{r['case'][3]}|{r['case'][6]}|{r['r41']['median_us']:.2f}|{r['native']['median_us']:.2f}|{r['cat0']['median_us']:.2f}|{r['cat1']['median_us']:.2f}|" for r in gemm['summary'])
full=load('full_audit.json');ft=[]
for c in sorted(set(tuple(r['case']) for r in full['runs'])):
 a=st.median(r['median_span_us'] for r in full['runs'] if tuple(r['case'])==c and r['version']=='r41')
 b=st.median(r['median_span_us'] for r in full['runs'] if tuple(r['case'])==c and r['version']=='fullcat1')
 ft.append(f'|{c[3]}|{c[6]}|{a:.2f}|{b:.2f}|{100*(b/a-1):+.2f}%|')
pre=load('preload_audit.json')
pt='\n'.join(f"|{r['case'][3]}|{r['case'][6]}|{r['native']['median_us']:.2f}|{r['pre0']['median_us']:.2f}|" for r in pre['summary'])
counter=load('detail_counters.json')
ct=[]
for item in counter:
 m=item['medians'];keys=['Task Duration(us)','aic_mac_time(us)','aic_mte1_time(us)','aic_mte2_time(us)','aiv_vec_time(us)']
 ct.append('|'+ '|'.join([item['version'],str(item['case'][3]),str(item['case'][6])]+[f'{m[k]:.2f}' if k in m else 'N/A' for k in keys])+'|')
report=f'''# Case12 突破路线实测：r65～r67

2026-10-01。用户同意复盘后的实施顺序。本轮已完成独立 FP32 GEMM 对照、完整设备归约对照，以及三版完整算子。**尚无达到准入标准的替换版，r41 保持主线，不建议本轮占用 Judge15 提交。**

## 结论

|版本|单独变化|8组中位耗时下降|范围|两窗口都更快|
|---|---|---:|---:|---:|
{short}

UnitFlag 是小收益，不能解释 Case12 与榜单的全部差距。转置恒等式已经真正实现并上卡，本实现整体退化。N 遍历错开有一致的小收益，保留 r67 供后续研究；不能把它与 r65 的比例直接相加，也不能据此预测隐藏 Case12。

另外发现了明确的精度风险：CATLASS Preload 的按核 K-shuffle，在抽样点积通过时仍会使完整 max/sum 的相消用例失败。该变体不作为候选，未继续测性能。

## 环境、范围与隔离

- 实卡 Ascend910_9362，ACL 查询20 Cube 核；CANN9.0.0、dav-2201。没有并发 NPU 测量。
- 基线 `v12_baseline_r41.asc`，SHA256 `1caf7870ac4154c0f555621ba9c41f4601c6ecee96cb2e8d0bf23acc4fc4f373`，未修改。
- 三版直接基于 r41，新增4入口：FP16/BF16 × TA0/1。完整入口保留旧r30资格、pitch/family条件，限定 `B=1,1280<=M<1536,4096<=N<6144,K=1536,TB=false`，排除r41专属路径。没有按实测最优 N 单点选择入口。
- 删除新模块和唯一入口 hook 后均能逐字节恢复 r41。
- 每版186配置、602次精度调用通过：164×3 加22×5；另有短测。覆盖N范围、两种dtype/TA、全负、零、大尺度、重复列、成对相消、M尾块和fallback。每次完整BMMS调用前NaN毒化输出。
- CPU参考使用实际量化后的输入进行FP64计算；容差 `1e-4+1e-4*abs(reference)`。通过并不等于所有输入的数学精度证明。
- r66另有128种合法尾块的GM→UB列归约离线检查；r67有83,664组N覆盖及预取下一块检查。均不是硬件竞争检测。
- 性能预先固定8配置：M1280/K1536/FP16/TB0，N4096/4160/5120/6080 × TA0/1。每版两窗口串行ABBA，每形状30次，丢弃前5次；核对新增kernel命中。
- 预先准入门槛：中位耗时下降≥5%、窗口方向一致、无未解决的>3%稳定退化。三版没有入围，因此未扩展32组筛选、96组独立性能留出，也未运行新的mssanitizer或Judge15。

## 完整算子性能

单位μs。每个候选使用自己的同期基线；正比例表示更快。都是轻量msprof task duration，非无profiler测量，不包含host内存分配/释放。

|版本|N|TA|同期r41|候选|耗时下降|
|---|---:|---:|---:|---:|---:|
{perf}

三版资源均为L1 384KiB、L0C128KiB。r65/r67的L0A/L0B双槽分别32/64KiB；r66交换为64/32KiB。r65只更换MMAD/FIX的UnitFlag交接，原GM环形缓冲READY/FREE保持。r66计算D=BᵀAᵀ后按D列取最大，仍沿原C的M/N分片写partial，没有引入20份新partial。r67完整K点积不变，只旋转N块顺序，最终sum(M)顺序保持。

## 独立 GEMM 标尺

固定本地CATLASS v1.4.0源码，保留许可证；输入FP16/BF16，**输出C保持FP32**，没有利用FP16中间结果掩盖耗时。

native从原r30生产者抽取，保持K顺序和原分核，改为完整C写出并去掉消费者信用等待；它也改变了写地址/协议，因此r41-native的差值不能严格解释成独立的“归约成本”。cat0/cat1分别为Pingpong关闭/开启UnitFlag，块128×256×256、L0 K64，固定swizzle<3,1>。它们不是CATLASS所有策略的最优值。

每个通过的GEMM变体148配置×2调用，检查全部C有限、67个CPU FP64点积和完整CPU max/sum；只有fullcat1额外检查设备归约。不是逐元素FP64全C对比。

第一批对照，每窗口25次、丢弃5次；r41是完整BMMS，其余三列仅GEMM，**不能直接比较为完整算子加速比**。

|N|TA|r41完整|native仅GEMM|cat0仅GEMM|cat1仅GEMM|
|---:|---:|---:|---:|---:|---:|
{gt}

无K-shuffle的Preload又进行了两窗口独立对照：

|N|TA|同期native仅GEMM|Preload仅GEMM|
|---:|---:|---:|---:|
{pt}

这些结果没有支持“换一个成熟GEMM就能普遍大幅突破”的判断；也不能证明当前实现已达到硬件上限。具体仍依赖输入stride、布局和调度。

## 完整 CATLASS + 设备归约

cat1的完整FP32 C随后由40 AIV核做逐行max，再由1个AIV核做sum。计时记录首kernel起点至末kernel终点的设备span，包含中间调度间隔；逐kernel时长另外归档。该归约是功能对照，没有宣称是最优归约实现。

|N|TA|同期r41|三kernel span|耗时增加|
|---:|---:|---:|---:|---:|
{chr(10).join(ft)}

逐行max段约27～32μs，sum约1μs。当前这个完整组合比融合基线慢21～31%，不能将纯GEMM局部优势直接外推到提交版本。148配置×2次设备输出检查通过。

## K-shuffle 的精度反例

优化Preload模板将每个核的K起点设为 `blockIdx % kTileCount`，完整计算全部K，但累加次序随核变化。case1144为FP16、M1280/N4160/K1536/TA0：B各列相同，A后半行是前半行的相反数，CPU FP64最终输出精确为0。

该版本67个抽样点积检查通过，但最终 `sum(max(C,N),M)` 误差约4.82948e-4，误差/容差=4.82948，大于1。初始4组短测和前144组精度通过也不能掩盖这个失败；在第145组停止，未测试余下3组或性能。

这是本轮最有约束力的发现之一：BMMS最终归约精度必须独立验证，不能只用GEMM的逐点容差或随机正输出来放行改变K顺序的优化。r65/r67保持原K顺序，r66也保持K遍历顺序；三版完整相消用例已通过。

## 流水线计数器

另采集N5120/TA0和N6080/TA1，各5次丢弃首个。下面是msprof计数器聚合值，单位μs；存在额外profiling开销、各流水线重叠，不能相加，也不是逐核关键路径证明。

|版本|N|TA|完整task|AIC MAC|AIC MTE1|AIC MTE2|AIV vector|
|---|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(ct)}

原始字段和每次采样在 `evidence/results/detail_counters.json`，不以计数器运行替代前面的ABBA性能结果。当前证据不足以把平台榜单差距归结为某一个单独阶段。

本轮计数器支持三个更具体的判断：

- **不能把转置失败归因于列归约更慢。** r66 的 AIV vector 时间反而更低，MTE1 也更低；但 MTE2 增加，完整时延未改善。减少某条流水线的工作，并不保证关键路径缩短。
- **N 遍历错开有输入加载方面的证据。** r67 的两个样本 MAC 基本不变，MTE2 从68.40/134.04降至64.28/131.31μs，完整task同时下降。它支持“访问调度有小幅优化空间”，尚不能证明具体是哪个缓存或内存银行冲突。
- **UnitFlag解决的是局部等待。** r65 在N5120时MAC、MTE1、MTE2基本不变而task下降；N6080/TA1没有同样收益。因此不能用消除整块等待来解释所有宽矩阵的时延。


## 决策与后续

1. 主线仍是r41。r65/r67保留为小收益研究分支，r66不晋升；K-shuffle反例不允许进入主线。
2. 已把上轮提出的UnitFlag和转置乘积从纸面方案变成实测，不再反复提为未经验证的突破口。
3. 若下一轮组合r65+r67，必须作为新版本重新实测，不能把两项收益相加。当前仅8组初筛，不能将其称为稳定泛化优化。
4. 若继续深挖隐藏Case12，应优先利用已有r58覆盖诊断结果确认N的stride分支（它不能直接确定TA或精确N），或补更直接的访存争用证据；不再根据约114μs倒猜shape。队友给出的区间与本地合成形状仍需区分。
5. 后续卡时不宜继续全部投入Case12；可将已经独立验证的低层改动迁移到9/10的短K簇做单独实验，保持既有收益入口隔离。

完整源码、README、manifest均位于 `BMMS_V12/v12_r65*` 至 `v12_r67*`。报告关联：[汇总](SUMMARY.json)、[性能CSV](PERFORMANCE.csv)、[证据包](rethink_evidence.tar.gz)。

证据包{len(manifest)}文件、{archive.stat().st_size:,}字节，SHA256 `{summary['archive']['sha256']}`，清单逐项校验通过。包含编译日志、验证输出、profiler CSV、初始及后续harness、固定CATLASS头文件和输入metadata/hash；没有重复归档大体积输入二进制。编译有已有legacy kernel type/SDK属性警告，退出成功不等于零警告。
'''
(out/'REPORT.md').write_text(report,encoding='utf-8')
mainfile=v/'MAINLINE.json';main=json.loads(mainfile.read_text(encoding='utf-8'))
for version in names:
 meta=json.loads((v/f'v12_{version}_manifest.json').read_text())
 assert not any(c['version']=='v12_'+version for c in main['candidates'])
 main['candidates'].append(dict(version='v12_'+version,file=f'v12_{version}_{names[version]}.asc',sha256=meta['sha256'],
     parent='v12_baseline_r41.asc',status=meta['status'],readme=f'v12_{version}_README.md',npu_report=meta['report']))
main.update(last_implemented_version='v12_r67',latest_experiment_report='../V12_npu_lab/results/rethink_20261001/REPORT.md',
 latest_experiment_outcome='r65/r66/r67 completed: 186 precision configurations/602 calls each passed; screen median reductions +1.05%/-1.94%/+2.22%. No candidate passes 5% gate. Independent GEMM audit completed; per-core K shuffle fails cancellation. Keep r41.',
 next_action='Keep r41. Retain r65/r67 as research; any combination needs a fresh independent trial. Use actual layout/coverage evidence before more Case12 traffic work; consider isolated transfer to short-K cases. Do not use failed K-shuffle.',recommended_candidate=None,active_candidate=None)
assert hashlib.sha256((v/'v12_baseline_r41.asc').read_bytes()).hexdigest()==main['accepted_sha256']
mainfile.write_text(json.dumps(main,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:summary[k] for k in names},indent=2));print('Archived files verified:',len(manifest))

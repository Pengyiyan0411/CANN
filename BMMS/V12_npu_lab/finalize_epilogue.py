from pathlib import Path
import json,hashlib,shutil
r=Path(__file__).resolve().parents[1];v=r/'BMMS_V12';o=r/'V12_npu_lab/results/parallel_epilogue_20260929'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def put(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
base=(v/'v12_baseline_r41.asc').read_bytes();assert hashlib.sha256(base).hexdigest()=='1caf7870ac4154c0f555621ba9c41f4601c6ecee96cb2e8d0bf23acc4fc4f373'
validation=read(o/'evidence/results/r48_r50_validation.json')
names={'r48':'v12_r48_case12_parallel_epilogue.asc','r49':'v12_r49_case12_fractional_guarded.asc','r50':'v12_r50_case12_deferred_partials.asc'}
statuses={'r48':'Rejected locally: all-active screen median reduction -0.02%; pN2/5 regress, pN20 median +1.03%; no broad benefit', 'r49':'Rejected for promotion: independent active subset 18/20 wins median +3.04%, but one geometry regresses 16.81% in both dtypes', 'r50':'Rejected locally: active screen median +0.07%, range -0.67% to +0.47%; no meaningful benefit'}
perf={tag:read(o/f'{tag}_analysis.json') for tag in ['r48_screen','r49_holdout','r50_screen']}
for ver,name in names.items():
    meta=read(v/f'v12_{ver}_manifest.json');src=(v/name).read_bytes();assert hashlib.sha256(src).hexdigest()==meta['sha256'];assert src==(o/f'evidence/{ver}.asc').read_bytes()
    ns='12'+ver[1:];s=src.decode();a=s.index('// BMMS'+ns+'_BEGIN');b=s.index('// BMMS'+ns+'_END',a)+len('// BMMS'+ns+'_END')
    s=s[:a]+s[b+2:];hook='    if(bmms'+ns+'::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
    assert s.replace(hook,'',1).encode()==base
    meta.update(status=statuses[ver],precision=validation[ver],judge_tested=False,report='../V12_npu_lab/results/parallel_epilogue_20260929/REPORT.md',sanitizer='Not rerun: performance candidates rejected; inherited limitations remain open.')
    put(v/f'v12_{ver}_manifest.json',meta)
# Verify r50 still uses exactly the original final merge and ReduceSum body.
s=(v/names['r50']).read_text();a=s.index('class RowMaxConsumer',s.index('namespace bmms1250 {'));a=s.index('        auto merged=mergedBuf.Get<float>(),tmp=tmpBuf.Get<float>();',a);b=s.index('} // namespace bmms1230',base.decode().index('class RowMaxConsumer',base.decode().index('namespace bmms1230 {')))
original=base.decode();c=original.index('        auto merged=mergedBuf.Get<float>(),tmp=tmpBuf.Get<float>();',original.index('class RowMaxConsumer',original.index('namespace bmms1230 {')))
assert original[c:b] in s[a:]

summary=dict(accepted='v12_r41',recommended_candidate=None,iterations=[{'version':x,'status':statuses[x],'precision':validation[x]} for x in names],performance={k:x['stats'] for k,x in perf.items()},counters=read(o/'COUNTERS.json'),evidence_files_verified=len(read(o/'evidence/manifest.json')['files']),static_audits={x:read(o/f'audit_{x}.json') for x in names},next_action='Prioritize GM->L1/ND->NZ and layout/task-order interactions; use new pM1 holdout already generated, separate cache evidence from arithmetic and epilogue. pN alone is not a safe selector.',sanitizer='No new sanitizer run; all three candidates rejected on performance; historical race/init and limited memcheck concerns remain unresolved.')
put(o/'SUMMARY.json',summary)

report='''# Case12 合并与写回拆分实验：r48–r50

## 决策与主要发现

**主线保留 v12_baseline_r41.asc，本轮不推荐新的性能提交。** 三版均完成代码、编译、数值验证和同机性能筛选；源码保留用于复现，未覆盖主线，也未生成失败候选的提交包。

1. 单独并行合并行最大值，或单独延后中间结果写回，未获得可靠收益；r47/r49 的较大局部收益不能主要归结为这两个动作。
2. r49 仅以原计划 `pN>=4` 选择路径仍不可靠：新形状出现约 16.81% 的退化。不能把上轮赢家直接推广到同一 pN 分组。
3. 一对获益/退化代表样本中，AIC 矩阵乘法时间基本保持，而 AIC MTE2 时间随端到端耗时同向明显变化。下一优先级转为 GM→L1 加载、ND→NZ 转换和任务顺序/layout 的相互影响；这是现有计数器支持的方向，尚未确定缓存、转换吞吐或等待的具体因果比例。

最新 Judge 仍是 r44 反馈：Case11=82.82μs，Case12=113.68μs，15 点 Pass。r48–r50 尚未在 Judge 测试，本文没有将合成输入收益当作隐藏 Case12 的收益。

## 排查与三轮修改

### r48：只并行化最终行 Max

复用 r30 的 `MacroMmadProducer`、原 pM/pN 与全部前段消费循环；每个 AIV 负责 64 行，通过一条带 stride 的 DataCopyPad 读取所有 N 分片，再合并最大值。新增一次 SyncAll，最后保持完整 M 的 ReduceSum。初筛 32 配置全部实际启用。

结果整体中位耗时下降 **−0.02%**。pN=2 的 10 配置全部退化，中位 −1.50%；pN=5 的 6 配置全部退化，中位 −0.48%；pN=20 的 16 配置中位 +1.03%，范围 +0.24%～+1.82%，其中 13 个在两个窗口都快。并行合并的收益与新增同步/搬运代价互相抵消，不晋升。

### r49：r47 加入原 pN>=4 门槛

设备代码与 r47 经 namespace 归一化后相同；只收紧 host 选择范围。门槛在新的 r48_holdout 性能测量前确定。该留出集预先按 pN=2/5/20 分层，16 种新几何/布局各测 FP16、BF16；M/N 组合不与前 282 配置重复。

32 配置中 20 个实际启用，18 快、2 慢，中位 **+3.04%**。但 `M=1472,N=4864,K=1600,TA=1,TB=0,pM=4,pN=5` 两种 dtype 都退化约 **16.81%**，两窗口复现。即使该形状的峰值 cells、输入行列和较旧版相比下降，也没有变快；静态成本不等于硬件时间。r49 不推荐提交。

原 pN=20 的 10 配置全部快，中位 +3.09%，范围 +0.54%～+8.84%。这是分层观察，不能在看完结果后直接把进一步收紧的门槛宣称为已独立验证的新候选。

### r50：只延后整段 M 的 partial 写回

保留 r30 原计算分块、producer 与最终 merge/ReduceSum，范围限定为 Case12 原 r30 路由、r41 展平门槛 FALSE、`pM=1,pN>=4,tasks=blocks`。每个 AIV 将所有 M 宏块的自身半行最大值保存在 UB，原来每个 M 宏块的一次 GM 写回改为末尾 1–2 次带 stride 的 DataCopyPad；不加第二次 SyncAll、不重排求和。

在已知 32 配置中 10 个启用，中位 **+0.07%**，范围 −0.67%～+0.47%，5 快、5 慢，只有 3 个两窗口都快。未得到明确收益，不晋升。另预先生成的 32 新性能留出配置仅完成数值验证，没有继续耗卡计时；`finish_r50.sh` 未执行，实际收尾使用 `finish_epilogue_analysis.sh`。

## 性能汇总

|版本|对照标杆|测量集总配置 / 启用配置|启用配置中位耗时下降|最差～最好|决策|
|---|---|---:|---:|---:|---|
|r48|同形状 r41|32 / 32|−0.02%|−1.87%～+1.82%|淘汰|
|r49|同形状 r41|32 / 20|+3.04%|−16.81%～+8.84%|淘汰|
|r50|同形状 r41|32 / 10|+0.07%|−0.67%～+0.47%|淘汰|

全部性能使用公共入口，一调用一个 kernel，通过实际 profiler kernel 名确认启用范围。每版两个独立进程窗口，串行 A/B、B/A；每配置 30 次，舍弃前 5 次，先取每窗口中位数再汇总。正数表示减少耗时。构造 shape 的同机标杆是 r41，CPU FP64 用于数值参考；Judge 右列 Case12=91.20μs 的未知 shape 与这些样本不能构成三方同形状性能比较。

完整逐配置基线/候选时间、窗口结果、启用与回退 kernel 名见 `PERFORMANCE.md` 和 `evidence/results/*_summary.json`。

## 代表样本的流水指标

选取 r49 中一慢一快的 FP16 样本，各用 PipeUtilization 和 Memory 两组独立 profiler 运行，与 r41 对照。每样本 5 次，舍弃首个 warm-up 后取中位数；每次输出也验证。以下指标不相加，因为各管线时间有重叠；硬件计数器运行不替代上述两个窗口的正式性能结果。

|样本|版本|任务时间 μs|AIC 时间 μs|MAC μs|MTE1 μs|MTE2 μs|AIV MTE3 μs|
|---|---|---:|---:|---:|---:|---:|---:|
|1472×4864×1600，TN，pN=5|r41|133.328|119.570|87.560|64.113|105.370|0.416|
|同上|r49|154.537|130.608|87.724|64.476|116.804|0.264|
|1440×4992×1568，NN，pN=20|r41|172.667|161.436|86.807|62.554|149.048|1.898|
|同上|r49|156.957|144.860|86.803|63.010|130.266|0.314|

这里观测到：较慢样本 AIC MTE2 增加约 11.43μs；较快样本减少约 18.78μs，MAC 基本不变。AIV 写回时间下降不能单独解释前者仍显著退化或后者约 15.71μs 的加速。与 r48/r50 拆分实验一起，更支持数据加载/调度交互是优先调查对象。Memory 组的 L2 read/write bandwidth 字段为 0，**不能据此断定没有 L2 流量或已识别缓存命中率**。目前没有完整逐核尾部等待证据。

下一轮先区分两项：固定原 grid 与算术，仅调整加载或相邻任务访问顺序；用新样本和可用的缓存/搬运指标检查收益是否跟布局、pitch、尾块有关。也可以在尚未计时的 r50 新 pM=1 集合上检验 r49 的局部收益是否继续成立，但不得用现有赢家作 shape 白名单。

## 数值、静态检查与资源

|版本|NPU 配置|每配置重复|普通数值调用|结果|
|---|---:|---:|---:|---|
|r48|282|3|846|全部 Pass|
|r49|314|3|942|全部 Pass|
|r50|366|3|1098|全部 Pass|

共 2,886 次候选普通数值调用，不含性能期间的逐次核对。r41 对新增数据也作对应数值检查。测试复用独立 C ABI harness，自行设计输入，使用实际量化后 FP16/BF16 的 CPU FP64 参考；容差 `1e-4+1e-4*abs(reference)`，每次输出先写 NaN。新输入包括负值、全零、宽尺度、重复列和正负成对相消。三版最大误差/容差比均为 0.076294，小于 1。r50 额外 52 配置包含 32 个新形状/dtype 配置和 20 个实际命中路径的特殊值配置，均通过。

三版真实 CANN 编译完成。CPU 结构枚举均覆盖 16,384 配置与 8 种核数：r48 6,054 个启用，r49 2,682 个启用，r50 599 个启用。检查分片范围、行写入覆盖、workspace 边界和 UB 预算；r50 校验 13,278,720 个 partial 元素均恰好写入一次，显式 UB 最大 87,104B。r48 显式 UB 最大 83,872B；r49 81,536B。CPU 模型不等于硬件异步竞争证明。

三版都只增加独立命名空间、8 个 device 入口及一个 host hook；移除这些内容可逐字节恢复 r41。r48、r50 直接复用原 producer；r50 最终归约正文与原 r30 完全一致。r41 主线 SHA256 仍为 `1caf7870ac4154c0f555621ba9c41f4601c6ecee96cb2e8d0bf23acc4fc4f373`。

由于三版均未通过性能晋升筛选，没有追加 sanitizer；历史 race/init 报告及 r41 有限 memcheck 超时仍未关闭。本轮未声称完整内存、竞争检测通过。

## 复现与文件

Ascend910_9362，20 Cube，CANN9.0.0，dav-2201。保持已有 standalone ASC/C ABI 工程，不改成 Torch 扩展。源码、全部构建日志、带 seed/hash 的数据描述、数值 JSONL、原始 profiler CSV 与二进制 SHA256 已归档。`r48_r50_evidence.zip` 的 221 个文件哈希与 ZIP CRC 已校验。

本地脚本和静态枚举见 `scripts/`、`audit_r48.cpp`、`audit_r49.cpp`、`audit_r50.cpp`；运行脚本按文件名 check_r48、check_r49、check_r50、finish_epilogue_analysis 顺序记录。不应复用已有 profiler tag。生成器可以重建大输入，归档不重复存储输入二进制。

源码在 `BMMS_V12/v12_r48_case12_parallel_epilogue.asc`、`v12_r49_case12_fractional_guarded.asc`、`v12_r50_case12_deferred_partials.asc`。它们均为未晋升实验记录；本轮没有新的 Judge 文件需要用户测试。
'''
(o/'REPORT.md').write_text(report,encoding='utf-8')
lines=['# 逐配置性能记录\n','耗时单位 μs；正数表示减少耗时。标杆均为同形状 r41。\n']
for tag in perf:
    d=read(o/f'evidence/results/{tag}_summary.json');ver=tag.split('_')[0];ns='bmms12'+ver[1:]
    active={x['case'][0] for x in d['runs'] if x['version']==ver and any(ns in k for k in x['kernels'])}
    lines += [f'## {tag}\n','|ID|M×N×K|dtype|TA/TB|启用|r41|候选|耗时下降|','|---|---|---|---|---|---:|---:|---:|']
    for x in d['summary']:
        i,B,M,N,K,dt,ta,tb=x['case'];delta=100*(1-x['candidate_median_us']/x['baseline_median_us'])
        lines.append(f'|{i}|{M}×{N}×{K}|{dt}|{ta}/{tb}|{i in active}|{x["baseline_median_us"]:.3f}|{x["candidate_median_us"]:.3f}|{delta:+.3f}%|')
    lines.append('')
(o/'PERFORMANCE.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

main=read(v/'MAINLINE.json')
for ver,name in names.items():
    meta=read(v/f'v12_{ver}_manifest.json');item=dict(version='v12_'+ver,file=name,parent='v12_baseline_r41.asc',sha256=meta['sha256'],status=statuses[ver],npu_report='../V12_npu_lab/results/parallel_epilogue_20260929/REPORT.md')
    main['candidates']=[x for x in main['candidates'] if x['version']!=item['version']]+[item]
main.update(latest_experiment_report='../V12_npu_lab/results/parallel_epilogue_20260929/REPORT.md',recommended_candidate=None,active_diagnostic=None,next_action=summary['next_action'])
put(v/'MAINLINE.json',main)
prior=r/'V12_npu_lab/results/b_resident_20260929/REPORT.md';s=prior.read_text(encoding='utf-8')
note='> 后续实验已完成：r48–r50 均未晋升，详细流水指标将优先级指向 AIC MTE2 搬运/调度交互。见 [后续报告](../parallel_epilogue_20260929/REPORT.md)。以下为当时记录。\n\n'
if not s.startswith('> 后续实验已完成：'):prior.write_text(note+s,encoding='utf-8')
priorj=r/'V12_npu_lab/results/b_resident_20260929/SUMMARY.json';j=read(priorj);j['subsequent_update']='../parallel_epilogue_20260929/REPORT.md';put(priorj,j)
prior_manifest=prior.parent/'LOCAL_MANIFEST.json'
if prior_manifest.exists():
    pm=read(prior_manifest)
    for updated in [prior,priorj]:pm['files'][str(updated.relative_to(prior.parent))]=hashlib.sha256(updated.read_bytes()).hexdigest()
    put(prior_manifest,pm)
scripts=o/'scripts';scripts.mkdir(exist_ok=True)
for name in ['prepare_r48.py','prepare_r49.py','prepare_r50.py','audit_r48.py','audit_r49.py','audit_r50.py','analyze_epilogue.py','analyze_epilogue_counters.py','finalize_epilogue.py']:
    shutil.copyfile(r/'V12_npu_lab'/name,scripts/name)
files=[p for p in o.rglob('*') if p.is_file() and p.name!='LOCAL_MANIFEST.json' and p.suffix!='.exe']
put(o/'LOCAL_MANIFEST.json',{'files':{str(p.relative_to(o)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}})
print(json.dumps({'accepted':main['accepted_version'],'recommended':None,'precision_calls':sum(x['calls'] for x in validation.values()),'verified_files':summary['evidence_files_verified']},ensure_ascii=False))
